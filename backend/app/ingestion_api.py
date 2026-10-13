import hashlib
import json
import secrets
import time
import os
import re
from datetime import datetime
from typing import Any
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import Response, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from .auth import get_learner
from .db import get_db, utcnow
from .models import Collection, Material, MaterialRevision, Citation, Job, ProviderConnection
from .jobs import enqueue
from .settings import settings
from .storage import get_storage
from .ingest import owned, queue_provision, reserve_source_quota
from .sources.base import SourceError
from .sources.local import SUPPORTED
from .sources.drive import SCOPES, encrypt_credentials, decrypt_credentials, DriveAdapter

router=APIRouter()

# Structural BCP 47 validation, bounded by the persisted column. This is an
# explicit learner label, not an unsupported claim of automatic detection.
_LANGUAGE_TAG = re.compile(r"(?:[a-z]{2,3}(?:-[a-z]{3}){0,3}|[a-z]{4}|[a-z]{5,8})(?:-[a-z]{4})?(?:-(?:[a-z]{2}|[0-9]{3}))?(?:-(?:[a-z0-9]{5,8}|[0-9][a-z0-9]{3}))*(?:-[0-9a-wy-z](?:-[a-z0-9]{2,8})+)*(?:-x(?:-[a-z0-9]{1,8})+)?", re.IGNORECASE)


def source_language_tag(value: str) -> str:
    if not isinstance(value, str) or len(value) > 30 or not _LANGUAGE_TAG.fullmatch(value):
        raise ValueError('invalid_source_language')
    parts = value.split('-')
    # Canonical common language/script/region casing; extensions stay lowercase.
    result = [parts[0].lower()]
    extension = False
    for part in parts[1:]:
        if len(part) == 1:
            extension = True
        result.append(part.lower() if extension else part.title() if len(part) == 4 and part.isalpha() else part.upper() if len(part) == 2 and part.isalpha() else part.lower())
    return '-'.join(result)


class SourceLanguageInput(BaseModel):
    source_language: str = Field(min_length=2, max_length=30)

    @field_validator('source_language')
    @classmethod
    def valid_language(cls, value: str) -> str:
        return source_language_tag(value)


class SourceLanguageDTO(BaseModel):
    material_id: str
    revision_id: str
    source_language: str


class IntakeDTO(BaseModel):
    material_id:str
    revision_id:str
    job_id:str
    status:str
    storage_state:str
    collection_id:str
    source_language:str

class MaterialStatusDTO(BaseModel):
    id:str
    title:str
    status:str
    collection_id:str
    current_revision_id:str|None
    revision_id:str|None
    storage_state:str|None
    error_code:str|None
    error_message:str|None
    source_language:str

class ConnectionDTO(BaseModel):
    provider:str
    status:str
    scopes:list[str]
    capabilities:dict[str,Any]
    last_sync:datetime|None
    error_code:str|None

class OAuthStartDTO(BaseModel):
    authorization_url:str
    disclosure:str

class DisconnectDTO(BaseModel):
    status:str
    revocation:str
    message:str|None=None

class ProvisionDTO(BaseModel):
    job_id:str
    status:str
    pending_mirrors:int

class CollectionStorageDTO(BaseModel):
    collection_id:str
    storage_mode:str
    folder_mode:str
    folder_id:str|None
    provisioning_state:str
    last_sync:datetime|None

class MaterialStorageDTO(BaseModel):
    material_id:str
    state:str
    origin:str|None
    drive_file_id:str|None
    provider_revision:str|None
    receipt:dict[str,Any]

class SyncDTO(BaseModel):
    job_id:str
    status:str




def require_owned(db,model,identifier,learner):
    try: return owned(db,model,identifier,learner.id)
    except SourceError as exc: raise HTTPException(404,exc.code) from exc


def dto(db,revision,job):
    material=db.get(Material,revision.material_id)
    return {'material_id':material.id,'revision_id':revision.id,'job_id':job.id,'status':material.status,'storage_state':revision.storage_state,'collection_id':material.collection_id,'source_language':revision.source_language}


def create_intake(db,learner,collection,filename,source_type,data,mime,key,url=None,source_language="und"):
    jobkey=f'intake:{collection.id}:{key}'
    existing=db.scalar(select(Job).where(Job.learner_id==learner.id,Job.idempotency_key==jobkey))
    fingerprint=hashlib.sha256(data if data is not None else url.encode()).hexdigest()
    if existing:
        revision=db.get(MaterialRevision,existing.payload['revision_id'])
        if revision.metadata_json.get('intake_fingerprint')!=fingerprint or revision.metadata_json.get('filename')!=filename or revision.metadata_json.get('intake_source_language','und')!=source_language: raise HTTPException(409,'idempotency_key_conflict')
        if existing.state=='staging' and data is not None:
            revision.private_blob_key=get_storage().put(learner.id,data);existing.state='queued';db.commit()
        return dto(db,revision,existing)
    try:reserve_source_quota(db,learner.id,collection.id,len(data or b''),new_material=True)
    except SourceError as exc:raise HTTPException(429,exc.code) from exc
    raced=db.scalar(select(Job).where(Job.learner_id==learner.id,Job.idempotency_key==jobkey))
    if raced:
        raced_revision=db.get(MaterialRevision,raced.payload['revision_id'])
        if raced_revision.metadata_json.get('intake_fingerprint')!=fingerprint or raced_revision.metadata_json.get('filename')!=filename or raced_revision.metadata_json.get('intake_source_language','und')!=source_language:raise HTTPException(409,'idempotency_key_conflict')
        db.commit();return dto(db,raced_revision,raced)
    material=Material(learner_id=learner.id,collection_id=collection.id,title=filename,source_type=source_type,position=db.scalar(select(func.count(Material.id)).where(Material.collection_id==collection.id)) or 0)
    db.add(material); db.flush()
    revision=MaterialRevision(learner_id=learner.id,collection_id=collection.id,material_id=material.id,content_hash=fingerprint,private_blob_key=None,mime=mime,size=len(data or b''),source_url=url,source_language=source_language,origin='ui_link' if url else 'ui_upload',storage_state='upload-pending' if collection.storage_mode=='drive' else 'local-only',metadata_json={'filename':filename,'intake_fingerprint':fingerprint,'upload_id':key,'intake_source_language':source_language,'source_language_provenance':'learner' if source_language!='und' else 'unknown'})
    db.add(revision); db.flush()
    job=enqueue(db,learner.id,'ingest-material',{'revision_id':revision.id},idempotency_key=jobkey)
    if data is not None:job.state='staging'
    db.commit()
    if data is not None:
        revision.private_blob_key=get_storage().put(learner.id,data);job.state='queued'
    db.commit(); return dto(db,revision,job)


@router.post('/collections/{collection_id}/materials',status_code=202,response_model=IntakeDTO)
@router.post('/collections/{collection_id}/materials/upload',status_code=202,response_model=IntakeDTO,include_in_schema=False)
async def upload(collection_id:str,file:UploadFile=File(...),idempotency_key:str|None=Form(None),source_language:str=Form("und"),request_key:str|None=Header(None,alias='Idempotency-Key'),db=Depends(get_db),learner=Depends(get_learner)):
    collection=require_owned(db,Collection,collection_id,learner)
    if collection.archived: raise HTTPException(409,'collection_archived')
    try: source_language=source_language_tag(source_language)
    except ValueError as exc: raise HTTPException(422,'invalid_source_language') from exc
    filename=Path(file.filename or 'source').name
    suffix=Path(filename).suffix.lower()
    if suffix not in SUPPORTED: raise HTTPException(415,'unsupported_type')
    idempotency_key=idempotency_key or request_key
    if not idempotency_key or not 1<=len(idempotency_key)<=150: raise HTTPException(422,'invalid_idempotency_key')
    data=await file.read(settings.max_upload_bytes+1)
    await file.close()
    if not data: raise HTTPException(422,'empty_source')
    if len(data)>settings.max_upload_bytes: raise HTTPException(413,'oversize')
    mime={'.pdf':'application/pdf','.md':'text/markdown','.txt':'text/plain','.csv':'text/csv','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png'}[suffix]
    return create_intake(db,learner,collection,filename,'photo' if suffix in {'.png','.jpg','.jpeg'} else suffix[1:],data,mime,idempotency_key,source_language=source_language)


class LinkInput(SourceLanguageInput):
    source_language: str = Field(default="und", min_length=2, max_length=30)
    url:str=Field(min_length=8,max_length=4096)
    idempotency_key:str|None=Field(None,min_length=1,max_length=150)


@router.post('/collections/{collection_id}/link',status_code=202,response_model=IntakeDTO)
@router.post('/collections/{collection_id}/materials/link',status_code=202,response_model=IntakeDTO,include_in_schema=False)
def link(collection_id:str,body:LinkInput,request_key:str|None=Header(None,alias='Idempotency-Key'),db=Depends(get_db),learner=Depends(get_learner)):
    from urllib.parse import urlsplit
    from .sources.publicweb import validate_url_syntax
    from .sources.captions import video_id
    collection=require_owned(db,Collection,collection_id,learner)
    if collection.archived: raise HTTPException(409,'collection_archived')
    try:
        parsed=urlsplit(body.url)
        if parsed.hostname in {'youtube.com','www.youtube.com','m.youtube.com','youtu.be','www.youtu.be'}:
            identifier=video_id(body.url); url=f'https://www.youtube.com/watch?v={identifier}'; kind='captions'
        else:
            validate_url_syntax(body.url)
            # Query parameters may contain credentials and are never stored in Drive receipts.
            if parsed.query: raise SourceError('url_query_not_allowed','Use a public page URL without query parameters; YouTube watch IDs are supported separately.')
            url=body.url; kind='web'
    except SourceError as exc: raise HTTPException(422,{'code':exc.code,'message':exc.message}) from exc
    key=body.idempotency_key or request_key
    if not key or len(key)>150: raise HTTPException(422,'invalid_idempotency_key')
    return create_intake(db,learner,collection,url,kind,None,'application/json',key,url,source_language=body.source_language)


@router.get('/materials/{material_id}',response_model=MaterialStatusDTO)
def material_status(material_id:str,db=Depends(get_db),learner=Depends(get_learner)):
    material=require_owned(db,Material,material_id,learner)
    revision=db.scalar(select(MaterialRevision).where(MaterialRevision.material_id==material.id,MaterialRevision.learner_id==learner.id).order_by(MaterialRevision.created_at.desc()))
    return {'id':material.id,'title':material.title,'status':material.status,'collection_id':material.collection_id,'current_revision_id':material.current_revision_id,'revision_id':revision.id if revision else None,'storage_state':revision.storage_state if revision else None,'error_code':revision.metadata_json.get('error_code') if revision else None,'error_message':revision.metadata_json.get('error_message') if revision else None,'source_language':revision.source_language if revision else 'und'}


@router.patch('/materials/{material_id}/source-language', response_model=SourceLanguageDTO)
def correct_source_language(material_id: str, body: SourceLanguageInput, db=Depends(get_db), learner=Depends(get_learner)):
    material = require_owned(db, Material, material_id, learner)
    collection = require_owned(db, Collection, material.collection_id, learner)
    if material.archived or collection.archived:
        raise HTTPException(409, 'material_archived')
    query = select(MaterialRevision).where(MaterialRevision.material_id == material.id, MaterialRevision.learner_id == learner.id)
    if material.current_revision_id:
        query = query.where(MaterialRevision.id == material.current_revision_id)
    else:
        query = query.order_by(MaterialRevision.created_at.desc())
    revision = db.scalar(query.with_for_update())
    if revision is None:
        raise HTTPException(409, 'source_revision_unavailable')
    revision.source_language = body.source_language
    revision.metadata_json = {**revision.metadata_json, 'source_language_provenance': 'learner'}
    # Only the label changes: immutable source hashes/text/locators and persisted
    # session turn payloads remain untouched.
    db.commit()
    return {'material_id': material.id, 'revision_id': revision.id, 'source_language': revision.source_language}


@router.get('/material-revisions/{revision_id}/original')
def original(revision_id:str,db=Depends(get_db),learner=Depends(get_learner)):
    revision=require_owned(db,MaterialRevision,revision_id,learner)
    if not revision.private_blob_key: raise HTTPException(404,'original_unavailable')
    data=get_storage().get(learner.id,revision.private_blob_key)
    return Response(data,media_type=revision.mime,headers={'Content-Disposition':'attachment','Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.get('/connections',response_model=list[ConnectionDTO])
def connections(db=Depends(get_db),learner=Depends(get_learner)):
    rows=db.scalars(select(ProviderConnection).where(ProviderConnection.learner_id==learner.id)).all()
    return [{'provider':r.provider,'status':r.status,'scopes':r.scopes,'capabilities':r.capability_json,'last_sync':r.last_sync,'error_code':r.error_code} for r in rows]


@router.post('/connections/drive/connect',response_model=OAuthStartDTO)
@router.get('/connections/drive/connect',include_in_schema=False,response_model=OAuthStartDTO)
def connect(db=Depends(get_db),learner=Depends(get_learner)):
    if not all((settings.drive_client_id,settings.drive_client_secret,settings.credentials_key)):
        raise HTTPException(503,{'code':'drive_unconfigured','message':'Configure runtime Google OAuth and encrypted token storage before connecting Drive.'})
    connection=db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id==learner.id,ProviderConnection.provider=='drive'))
    if not connection:
        connection=ProviderConnection(learner_id=learner.id,provider='drive'); db.add(connection);db.flush()
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    import base64
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    connection.checkpoint={**connection.checkpoint,'oauth_state_hash':hashlib.sha256(state.encode()).hexdigest(),'oauth_verifier':encrypt_credentials({'verifier':verifier}),'oauth_expires_at':time.time()+600}
    db.commit()
    query={'client_id':settings.drive_client_id,'redirect_uri':settings.public_url.rstrip('/')+'/api/v1/connections/drive/callback','response_type':'code','scope':' '.join(SCOPES),'state':state,'access_type':'offline','prompt':'consent','code_challenge':challenge,'code_challenge_method':'S256'}
    return {'authorization_url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(query),'disclosure':'Creates/writes app-managed Collection folders. Read-only scope permits direct-drop discovery; app reads only bound folders. Live direct-drop visibility still requires verification.'}


@router.get('/connections/drive/callback')
def callback(state:str='',code:str='',error:str='',db=Depends(get_db),learner=Depends(get_learner)):
    connection=db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id==learner.id,ProviderConnection.provider=='drive'))
    checkpoint=connection.checkpoint if connection else {}
    if not state or checkpoint.get('oauth_expires_at',0)<time.time() or not secrets.compare_digest(checkpoint.get('oauth_state_hash',''),hashlib.sha256(state.encode()).hexdigest()): raise HTTPException(400,'oauth_state_invalid')
    verifier=decrypt_credentials(checkpoint['oauth_verifier'])['verifier']
    connection.checkpoint={k:v for k,v in checkpoint.items() if not k.startswith('oauth_')}; db.commit()
    if error or not code: raise HTTPException(400,'oauth_denied')
    try:
        response=httpx.post('https://oauth2.googleapis.com/token',data={'client_id':settings.drive_client_id,'client_secret':settings.drive_client_secret,'code':code,'redirect_uri':settings.public_url.rstrip('/')+'/api/v1/connections/drive/callback','grant_type':'authorization_code','code_verifier':verifier},timeout=20)
        if response.status_code!=200: raise HTTPException(502,'oauth_token_exchange_failed')
        credentials=response.json();scopes=credentials.get('scope','').split()
        if not set(SCOPES)<=set(scopes): raise HTTPException(403,'drive_scope_incomplete')
        if not credentials.get('refresh_token'): raise HTTPException(403,'drive_refresh_token_missing')
        credentials['expires_at']=time.time()+credentials.get('expires_in',3600)
        connection.encrypted_credentials=encrypt_credentials(credentials); connection.scopes=scopes; connection.status='connected'; connection.error_code=None
        connection.capability_json={'managed_writes':'authorized-unverified','direct_drop':'authorized-unverified','live_gates':'blocked-pending-provider-tests'}
        queue_provision(db,learner.id)
        db.commit()
    except httpx.HTTPError as exc: raise HTTPException(502,'oauth_network') from exc
    return RedirectResponse(settings.frontend_url.rstrip('/')+'/connections?drive=connected')


@router.delete('/connections/drive',response_model=DisconnectDTO)
@router.post('/connections/drive/disconnect',include_in_schema=False,response_model=DisconnectDTO)
def disconnect(db=Depends(get_db),learner=Depends(get_learner)):
    connection=db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id==learner.id,ProviderConnection.provider=='drive'))
    if not connection: return {'status':'disconnected','revocation':'no-credentials'}
    encrypted=connection.encrypted_credentials
    connection.encrypted_credentials=None;connection.status='disconnected';connection.scopes=[];connection.checkpoint={};db.commit()
    jobs=db.scalars(select(Job).where(Job.learner_id==learner.id,Job.kind.in_(['drive-sync','drive-provision','ingest-material']),Job.state.in_(['queued','running']))).all()
    for job in jobs:
        if job.kind=='ingest-material':
            revision=db.get(MaterialRevision,job.payload.get('revision_id'))
            if not revision or db.get(Collection,revision.collection_id).storage_mode!='drive': continue
        job.state='cancelled';job.lease_owner=None;job.lease_until=None
    collections=db.scalars(select(Collection).where(Collection.learner_id==learner.id,Collection.storage_mode=='drive')).all()
    for value in collections:value.provisioning_state='disconnected'
    db.commit(); revoked=False
    if encrypted:
        try: revoked=DriveAdapter(decrypt_credentials(encrypted)).revoke()
        except (SourceError,httpx.HTTPError): pass
    return {'status':'disconnected','revocation':'confirmed' if revoked else 'provider-unconfirmed','message':'Local tokens were deleted; Drive access stopped.'}


@router.post('/collections/{collection_id}/enable-drive',status_code=202,response_model=ProvisionDTO)
def enable_drive(collection_id:str,db=Depends(get_db),learner=Depends(get_learner)):
    collection=require_owned(db,Collection,collection_id,learner)
    from .ingest import connection_for
    try:connection_for(db,learner.id)
    except SourceError as exc:raise HTTPException(409,exc.code) from exc
    collection.storage_mode='drive';job=queue_provision(db,learner.id,collection.id)
    revisions=db.scalars(select(MaterialRevision).where(MaterialRevision.learner_id==learner.id,MaterialRevision.collection_id==collection.id,MaterialRevision.storage_state=='local-only')).all()
    for revision in revisions:
        revision.storage_state='upload-pending'
        # Re-run original pipeline; immutable chunks are reused after confirmed mirror.
        enqueue(db,learner.id,'ingest-material',{'revision_id':revision.id,'mirror':True},idempotency_key=f'mirror:{revision.id}')
    db.commit();return {'job_id':job.id,'status':'folder-provisioning','pending_mirrors':len(revisions)}

@router.post('/collections/{collection_id}/drive-folder/provision',status_code=202,response_model=ProvisionDTO)
def provision_collection(collection_id:str,db=Depends(get_db),learner=Depends(get_learner)):
    collection=require_owned(db,Collection,collection_id,learner)
    if collection.archived:raise HTTPException(409,'collection_archived')
    return enable_drive(collection_id,db,learner)

@router.get('/collections/{collection_id}/storage-status',response_model=CollectionStorageDTO)
def collection_storage(collection_id:str,db=Depends(get_db),learner=Depends(get_learner)):
    collection=require_owned(db,Collection,collection_id,learner)
    return {'collection_id':collection.id,'storage_mode':collection.storage_mode,'folder_mode':collection.folder_mode,'folder_id':collection.drive_folder_id,'provisioning_state':collection.provisioning_state,'last_sync':collection.last_sync}

@router.get('/materials/{material_id}/storage-status',response_model=MaterialStorageDTO)
def material_storage(material_id:str,db=Depends(get_db),learner=Depends(get_learner)):
    material=require_owned(db,Material,material_id,learner)
    revision=db.scalar(select(MaterialRevision).where(MaterialRevision.material_id==material.id,MaterialRevision.learner_id==learner.id).order_by(MaterialRevision.created_at.desc()))
    return {'material_id':material.id,'state':revision.storage_state if revision else 'pending','origin':revision.origin if revision else None,'drive_file_id':revision.drive_file_id if revision else None,'provider_revision':revision.provider_revision if revision else None,'receipt':revision.storage_receipt if revision else {}}


@router.post('/collections/{collection_id}/sync',status_code=202,response_model=SyncDTO)
def sync(collection_id:str,db=Depends(get_db),learner=Depends(get_learner)):
    collection=require_owned(db,Collection,collection_id,learner)
    if collection.storage_mode!='drive' or collection.provisioning_state!='ready':raise HTTPException(409,'drive_folder_not_ready')
    pending=db.scalar(select(Job).where(Job.learner_id==learner.id,Job.kind=='drive-sync',Job.entity_id==collection.id,Job.state.in_(['queued','running'])))
    if pending:
        if pending.state=='queued':pending.run_at=utcnow()
        job=pending
    else:job=enqueue(db,learner.id,'drive-sync',{'collection_id':collection.id},idempotency_key=f'manual-sync:{collection.id}:{uuid4()}')
    db.commit();return {'job_id':job.id,'status':job.state}

from .speech import router as speech_router
router.include_router(speech_router)
