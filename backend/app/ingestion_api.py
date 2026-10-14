import hashlib
import json
import secrets
import time
import os
import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Literal
from pathlib import Path
from urllib.parse import urlencode
from uuid import uuid4
import httpx
from fastapi import APIRouter, Depends, File, Form, Header, HTTPException, Query, UploadFile
from fastapi.responses import Response, RedirectResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select, func
from .auth import get_learner
from .db import get_db, utcnow
from .models import Collection, Material, MaterialRevision, Citation, Job, ProviderConnection
from .core_schemas import PdfPageManifestDTO, PdfPageCorrectionDTO, UploadLimitsDTO
from .jobs import enqueue
from .settings import settings
from .storage import get_storage
from .ingest import (owned, queue_provision, reserve_source_quota,
                     _manifest_review_pages, _schedule_pdf_finalize)
from .ingest_limits import (MAX_PDF_CORRECTION_BYTES, MAX_PDF_EXTRACTED_BYTES,
                            MAX_PDF_PAGE_RESPONSE_CHARS, MAX_UPLOAD_BYTES)
from .sources.base import SourceError
from .sources.local import SUPPORTED
from .sources.drive import SCOPES, encrypt_credentials, decrypt_credentials, DriveAdapter, connection_setup_state

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


class PdfPageCorrectionInput(BaseModel):
    model_config = {'extra': 'forbid'}
    expected_version: int = Field(ge=1)
    text: str = Field(max_length=2 * 1024 * 1024)


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


@router.get('/ingestion/limits',response_model=UploadLimitsDTO)
def upload_limits(learner=Depends(get_learner)):
    return {'max_upload_bytes':max(0,min(settings.max_upload_bytes,MAX_UPLOAD_BYTES))}

class ConnectionDTO(BaseModel):
    provider:str
    status:str
    scopes:list[str]
    capabilities:dict[str,Any]
    last_sync:datetime|None
    error_code:str|None
    configured:bool=False
    setup_state:Literal['demo','unconfigured','ready']|None=None

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
    max_upload_bytes=min(settings.max_upload_bytes,MAX_UPLOAD_BYTES)
    data=await file.read(max_upload_bytes+1)
    await file.close()
    if not data: raise HTTPException(422,'empty_source')
    if len(data)>max_upload_bytes: raise HTTPException(413,'oversize')
    mime={
        '.pdf':'application/pdf','.md':'text/markdown','.markdown':'text/markdown','.txt':'text/plain',
        '.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.rst':'text/plain',
        '.csv':'text/csv','.tsv':'text/tab-separated-values','.xlsx':'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        '.xlsm':'application/vnd.ms-excel.sheet.macroEnabled.12','.json':'application/json','.yaml':'text/yaml','.yml':'text/yaml',
        '.log':'text/plain','.jpg':'image/jpeg','.jpeg':'image/jpeg','.png':'image/png'
    }[suffix]
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


def _pdf_revision_for_material(db,material,learner_id):
    query=select(MaterialRevision).where(
        MaterialRevision.material_id==material.id,
        MaterialRevision.learner_id==learner_id,
    )
    if material.current_revision_id:
        query=query.where(MaterialRevision.id==material.current_revision_id)
    else:
        query=query.order_by(MaterialRevision.created_at.desc())
    revision=db.scalar(query)
    if not revision or Path(revision.metadata_json.get('filename','')).suffix.lower()!='.pdf':
        raise HTTPException(409,'pdf_revision_unavailable')
    manifest=revision.metadata_json.get('ingestion_manifest')
    if not isinstance(manifest,dict) or not manifest.get('pages'):
        raise HTTPException(409,'pdf_manifest_unavailable')
    return revision,deepcopy(manifest)


@router.get('/materials/{material_id}/ingestion-pages',response_model=PdfPageManifestDTO)
def pdf_ingestion_pages(material_id:str,cursor:int=Query(0,ge=0),limit:int=Query(40,ge=1,le=40),
                        db=Depends(get_db),learner=Depends(get_learner)):
    material=require_owned(db,Material,material_id,learner)
    revision,manifest=_pdf_revision_for_material(db,material,learner.id)
    pages=manifest.get('pages',[])
    batches={int(batch['index']):batch for batch in manifest.get('batches',[])}
    result_cache={}
    items=[]
    for page in pages[cursor:cursor+limit]:
        batch_index=(int(page['page_number'])-1)//int(manifest.get('batch_size',40))
        batch=batches.get(batch_index,{})
        key=batch.get('result_blob_key')
        extracted=''
        if key:
            if key not in result_cache:
                try:
                    result_cache[key]=json.loads(get_storage().get(learner.id,key))
                except Exception as exc:
                    raise HTTPException(409,'pdf_page_data_unavailable') from exc
            value=result_cache[key]
            if value.get('revision_id')!=revision.id or value.get('batch_index')!=batch_index:
                raise HTTPException(409,'pdf_page_data_binding_invalid')
            extracted='\n\n'.join(
                section.get('text','') for section in value.get('sections',[])
                if int(section.get('locator',{}).get('page',0))==int(page['page_number'])
            )
        items.append({**page,'text':extracted[:MAX_PDF_PAGE_RESPONSE_CHARS],
                      'text_truncated':len(extracted)>MAX_PDF_PAGE_RESPONSE_CHARS})
    return {
        'material_id':material.id,'revision_id':revision.id,'version':material.version,
        'status':manifest.get('status'),'warning':manifest.get('warning'),
        'page_count':manifest.get('page_count',len(pages)),
        'processed_pages':manifest.get('processed_pages',0),
        'review_required_count':manifest.get('review_required_count',0),
        'original_url':f'/api/v1/material-revisions/{revision.id}/original?inline=true',
        'items':items,'total':len(pages),
        'next_cursor':cursor+len(items) if cursor+len(items)<len(pages) else None,
    }


@router.patch('/materials/{material_id}/ingestion-pages/{page_number}',response_model=PdfPageCorrectionDTO)
def correct_pdf_ingestion_page(material_id:str,page_number:int,body:PdfPageCorrectionInput,
                               db=Depends(get_db),learner=Depends(get_learner)):
    material=require_owned(db,Material,material_id,learner)
    material=db.scalar(select(Material).where(Material.id==material.id,Material.learner_id==learner.id).with_for_update())
    collection=require_owned(db,Collection,material.collection_id,learner)
    if material.archived or material.status=='deleting' or collection.archived:
        raise HTTPException(409,'material_not_editable')
    if material.version!=body.expected_version:
        raise HTTPException(409,'version_conflict')
    revision,manifest=_pdf_revision_for_material(db,material,learner.id)
    if manifest.get('status') in {'ready','failed'}:
        raise HTTPException(409,'pdf_review_closed')
    pages=[dict(page) for page in manifest['pages']]
    if page_number<1 or page_number>len(pages):
        raise HTTPException(404,'page_not_found')
    page=pages[page_number-1]
    if int(page.get('page_number',0))!=page_number or page.get('status') not in {'needs-review','failed'}:
        raise HTTPException(409,'page_not_reviewable')
    correction_bytes=body.text.encode('utf-8')
    if len(correction_bytes)>MAX_PDF_CORRECTION_BYTES:
        raise HTTPException(413,'pdf_page_correction_limit')

    batch_index=(page_number-1)//int(manifest.get('batch_size',40))
    batches=[dict(batch) for batch in manifest.get('batches',[])]
    if batch_index>=len(batches) or not batches[batch_index].get('result_blob_key'):
        raise HTTPException(409,'pdf_page_data_unavailable')
    batch=batches[batch_index]
    try:
        value=json.loads(get_storage().get(learner.id,batch['result_blob_key']))
    except Exception as exc:
        raise HTTPException(409,'pdf_page_data_unavailable') from exc
    if value.get('revision_id')!=revision.id or value.get('batch_index')!=batch_index:
        raise HTTPException(409,'pdf_page_data_binding_invalid')

    sections=[
        section for section in value.get('sections',[])
        if int(section.get('locator',{}).get('page',0))!=page_number
    ]
    chapter_path=list(page.get('chapter_path',[]))
    corrected_text=body.text.strip()
    if corrected_text:
        heading_path=chapter_path
        title=' / '.join(heading_path) if heading_path else f'Page {page_number}'
        sections.append({
            'title':title,'text':corrected_text,'locator_kind':'pdf',
            'locator':{
                'page':page_number,'page_start':page_number,'page_end':page_number,
                'reading_method':'learner-correction','chapter_path':chapter_path,
                'heading_path':heading_path,
            },
        })
    sections.sort(key=lambda section:(
        int(section.get('locator',{}).get('page',0)),
        int(section.get('locator',{}).get('section_char_start',0)),
    ))
    old_key=batch['result_blob_key']
    page_results=[dict(item) for item in value.get('page_results',[])]
    for page_result in page_results:
        if int(page_result.get('page_number',0))==page_number:
            page_result.update(
                status='corrected' if corrected_text else 'blank',
                method='learner-correction' if corrected_text else 'learner-confirmed-blank',
                warning=None,text_chars=len(corrected_text),
                section_count=1 if corrected_text else 0,
            )
    result={'revision_id':revision.id,'batch_index':batch_index,
            'sections':sections,'page_results':page_results}
    result_bytes=json.dumps(result,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    new_batch_text_bytes=sum(len(str(section.get('text','')).encode('utf-8')) for section in sections)
    new_total=int(manifest.get('extracted_text_bytes',0))-int(batch.get('extracted_text_bytes',0))+new_batch_text_bytes
    if new_total>MAX_PDF_EXTRACTED_BYTES:
        raise HTTPException(413,'pdf_extracted_text_limit')
    new_key=get_storage().put(learner.id,result_bytes,f'{material.id}-pages-{batch_index}.json')
    page.update(
        status='corrected' if corrected_text else 'blank',
        method='learner-correction' if corrected_text else 'learner-confirmed-blank',
        warning=None,text_chars=len(corrected_text),
        section_count=1 if corrected_text else 0,
        correction_hash=hashlib.sha256(correction_bytes).hexdigest(),
        corrected_at=utcnow().isoformat(),
    )
    old_result_bytes=int(batch.get('result_bytes',0))
    batch.update(result_blob_key=new_key,result_bytes=len(result_bytes),
                 extracted_text_bytes=new_batch_text_bytes)
    manifest['pages']=pages
    manifest['batches']=batches
    manifest['batch_result_bytes']=int(manifest.get('batch_result_bytes',0))-old_result_bytes+len(result_bytes)
    manifest['extracted_text_bytes']=new_total
    obsolete=set(manifest.get('obsolete_result_blob_keys',[]))
    if old_key!=new_key:
        obsolete.add(old_key)
    manifest['obsolete_result_blob_keys']=sorted(obsolete)
    _manifest_review_pages(manifest)
    all_batches_complete=all(item.get('state')=='completed' for item in batches)
    if not manifest['review_required_count'] and all_batches_complete:
        _schedule_pdf_finalize(db,revision,manifest)
        material.status='processing'
    elif manifest['review_required_count']:
        manifest['status']='needs-review' if all_batches_complete else 'processing'
        material.status='needs-attention' if all_batches_complete else 'processing'
    else:
        manifest['status']='processing'
        material.status='processing'
    revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest}
    material.version+=1
    db.commit()
    return {'material_id':material.id,'revision_id':revision.id,'page_number':page_number,
            'status':page['status'],'version':material.version,
            'review_required_count':manifest['review_required_count'],
            'material_status':material.status,'finalize_job_id':manifest.get('finalize_job_id')}


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
def original(revision_id:str,inline:bool=False,db=Depends(get_db),learner=Depends(get_learner)):
    revision=require_owned(db,MaterialRevision,revision_id,learner)
    if not revision.private_blob_key: raise HTTPException(404,'original_unavailable')
    data=get_storage().get(learner.id,revision.private_blob_key)
    disposition='inline; filename="source.pdf"' if inline and revision.mime=='application/pdf' else 'attachment'
    return Response(data,media_type=revision.mime,headers={'Content-Disposition':disposition,'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})


@router.get('/connections',response_model=list[ConnectionDTO])
def connections(db=Depends(get_db),learner=Depends(get_learner)):
    rows=db.scalars(select(ProviderConnection).where(ProviderConnection.learner_id==learner.id)).all()
    setup = connection_setup_state()
    result = [{'provider':r.provider,'status':r.status,'scopes':r.scopes,'capabilities':r.capability_json,'last_sync':r.last_sync,'error_code':r.error_code,
               'configured':setup=='ready' if r.provider=='drive' else False,
               'setup_state':setup if r.provider=='drive' else None} for r in rows]
    if not any(r.provider=='drive' for r in rows):
        result.append({'provider':'drive','status':'disconnected','scopes':[], 'capabilities':{},'last_sync':None,'error_code':None,
                       'configured':setup=='ready','setup_state':setup})
    return result


@router.post('/connections/drive/connect',response_model=OAuthStartDTO)
@router.get('/connections/drive/connect',include_in_schema=False,response_model=OAuthStartDTO)
def connect(db=Depends(get_db),learner=Depends(get_learner)):
    setup = connection_setup_state()
    if setup == 'demo':
        raise HTTPException(503,{'code':'drive_demo_unavailable','message':'Google Drive is unavailable in the offline demo. Start the connected version and sign in.'})
    if setup != 'ready':
        raise HTTPException(503,{'code':'drive_unconfigured','message':'Configure runtime Google OAuth and encrypted token storage before connecting Drive.'})
    connection=db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id==learner.id,ProviderConnection.provider=='drive'))
    if not connection:
        connection=ProviderConnection(learner_id=learner.id,provider='drive'); db.add(connection);db.flush()
    state=secrets.token_urlsafe(32);verifier=secrets.token_urlsafe(48)
    import base64
    challenge=base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    connection.checkpoint={**connection.checkpoint,'oauth_state_hash':hashlib.sha256(state.encode()).hexdigest(),'oauth_verifier':encrypt_credentials({'verifier':verifier}),'oauth_expires_at':time.time()+600}
    db.commit()
    query={'client_id':settings.drive_client_id,'redirect_uri':settings.drive_redirect_uri,'response_type':'code','scope':' '.join(SCOPES),'state':state,'access_type':'offline','prompt':'consent','code_challenge':challenge,'code_challenge_method':'S256'}
    return {'authorization_url':'https://accounts.google.com/o/oauth2/v2/auth?'+urlencode(query),'disclosure':'Creates/writes app-managed Collection folders. Read-only scope permits direct-drop discovery; app reads only bound folders. Live direct-drop visibility still requires verification.'}


@router.get('/connections/drive/callback')
def callback(state:str='',code:str='',error:str='',db=Depends(get_db),learner=Depends(get_learner)):
    connection=db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id==learner.id,ProviderConnection.provider=='drive'))
    checkpoint=connection.checkpoint if connection else {}
    if not state or checkpoint.get('oauth_expires_at',0)<time.time() or not secrets.compare_digest(checkpoint.get('oauth_state_hash',''),hashlib.sha256(state.encode()).hexdigest()): raise HTTPException(400,'oauth_state_invalid')
    verifier=decrypt_credentials(checkpoint['oauth_verifier'])['verifier']
    connection.checkpoint={k:v for k,v in checkpoint.items() if not k.startswith('oauth_')}; db.commit()
    def consent_failure(reason):
        connection.error_code=reason; db.commit()
        return RedirectResponse(settings.frontend_url.rstrip('/')+'/connections?drive_error='+reason)
    if error or not code:return consent_failure('oauth_denied')
    try:
        response=httpx.post('https://oauth2.googleapis.com/token',data={'client_id':settings.drive_client_id,'client_secret':settings.drive_client_secret,'code':code,'redirect_uri':settings.drive_redirect_uri,'grant_type':'authorization_code','code_verifier':verifier},timeout=20)
        if response.status_code!=200:return consent_failure('oauth_token_exchange_failed')
        credentials=response.json()
        if not isinstance(credentials,dict) or not isinstance(credentials.get('scope'),str) or not isinstance(credentials.get('access_token'),str) or not credentials['access_token']:
            return consent_failure('oauth_token_exchange_failed')
        scopes=credentials['scope'].split()
        if not set(SCOPES)<=set(scopes):return consent_failure('drive_scope_incomplete')
        if not isinstance(credentials.get('refresh_token'),str) or not credentials['refresh_token']:return consent_failure('drive_refresh_token_missing')
        expires_in=float(credentials.get('expires_in',3600))
        if not 0<expires_in<=86400:return consent_failure('oauth_token_exchange_failed')
        credentials['expires_at']=time.time()+expires_in
        connection.encrypted_credentials=encrypt_credentials(credentials); connection.scopes=scopes; connection.status='connected'; connection.error_code=None
        connection.capability_json={'managed_writes':'authorized-unverified','direct_drop':'authorized-unverified','live_gates':'blocked-pending-provider-tests'}
        queue_provision(db,learner.id)
        db.commit()
    except (httpx.HTTPError,ValueError,TypeError):return consent_failure('oauth_network')
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
    from sqlalchemy import update
    from .db import as_utc
    # Serialize simultaneous Sync clicks, including SQLite where FOR UPDATE
    # does not lock rows. No provider request occurs in this short transaction.
    db.execute(update(Collection).where(Collection.id==collection.id,Collection.learner_id==learner.id).values(id=Collection.id))
    pending=db.scalar(select(Job).where(Job.learner_id==learner.id,Job.kind=='drive-sync',Job.entity_id==collection.id,Job.state.in_(['queued','running']))
                      .order_by((Job.state=='running').desc(),Job.run_at,Job.created_at))
    sleeping_poll = (pending is not None and pending.state=='queued' and as_utc(pending.run_at)>utcnow()
                     and bool(pending.idempotency_key and pending.idempotency_key.startswith(('poll:','initial-poll:'))))
    if pending and not sleeping_poll:
        job=pending
    else:
        # Admit/rate-account the user's request before replacing maintenance.
        # A rejected admission leaves the existing scheduled poll intact.
        job=enqueue(db,learner.id,'drive-sync',{'collection_id':collection.id},idempotency_key=f'manual-sync:{collection.id}:{uuid4()}')
        if sleeping_poll:
            pending.state='cancelled';pending.lease_owner=None;pending.lease_until=None
    db.commit();return {'job_id':job.id,'status':job.state}

from .speech import router as speech_router
router.include_router(speech_router)
