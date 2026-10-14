"""One immutable pipeline for local, UI-to-Drive, links and direct folder drops."""
import hashlib
import json
import os
import math
import re
from uuid import uuid5, NAMESPACE_URL
import jsonschema
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select, func, update
from .models import Learner, Collection, Material, MaterialRevision, Chunk, Concept, Citation, ProviderConnection, SourceWriteReceipt, Job
from .db import utcnow
from .jobs import enqueue, register, NeedsAttention, RetryableJobError, assert_lease
from .storage import get_storage
from .settings import settings
from .sources.base import SourceError, SourceSnapshot, ExtractedSection
from .sources.local import extract_file, SUPPORTED
from .sources.publicweb import fetch_public_page
from .sources.captions import extract_captions
from .sources.drive import DriveAdapter, decrypt_credentials, encrypt_credentials, READ_SCOPE, WRITE_SCOPE

EXTRACTION_VERSION = 'source-excerpts-v1'


def owned(db, model, identifier, learner_id):
    value=db.scalar(select(model).where(model.id==identifier,model.learner_id==learner_id))
    if not value: raise SourceError('not_found','The requested source is unavailable.')
    return value


def reserve_source_quota(db,learner_id,collection_id,size,revision_id=None,new_material=False):
    """Serialize tenant reservations before inserting/updating revision.size.

    Caller persists its reservation in the same transaction before blob/network work.
    Existing revision bytes are replaced, not double-counted on retry.
    """
    if size<0 or size>settings.max_upload_bytes:raise SourceError('oversize','The source exceeds the upload limit.')
    # Flush prior completed stages before taking the short quota lock.
    db.commit()
    # The owner row serializes all source paths on PostgreSQL; SQLite's UPDATE
    # obtains its write lock before SUM, preventing two stale read reservations.
    db.execute(update(Learner).where(Learner.id==learner_id).values(id=Learner.id))
    totals=select(func.coalesce(func.sum(MaterialRevision.size),0)).where(MaterialRevision.learner_id==learner_id)
    if revision_id:totals=totals.where(MaterialRevision.id!=revision_id)
    used=db.scalar(totals) or 0
    count=db.scalar(select(func.count(Material.id)).where(Material.learner_id==learner_id,Material.collection_id==collection_id)) or 0
    if used+size>int(os.getenv('SOURCE_QUOTA_BYTES','209715200')) or (new_material and count>=int(os.getenv('SOURCE_MAX_MATERIALS','1000'))):
        db.rollback()
        raise SourceError('source_quota_exceeded','This learner or Collection has reached its source quota.')


def connection_for(db,learner_id):
    connection=db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id==learner_id,ProviderConnection.provider=='drive'))
    if not connection or connection.status!='connected' or not connection.encrypted_credentials:
        raise SourceError('drive_disconnected','Connect Drive before saving to this Collection.',True)
    if not {WRITE_SCOPE,READ_SCOPE} <= set(connection.scopes): raise SourceError('drive_scope','Drive write and direct-drop read consent are required.')
    return connection


def drive_adapter(db,learner_id):
    connection=connection_for(db,learner_id)
    def persist(value):
        connection.encrypted_credentials=encrypt_credentials(value); db.commit()
    return DriveAdapter(decrypt_credentials(connection.encrypted_credentials),persist)


def queue_provision(db,learner_id,collection_id=None):
    key=f'drive-provision:{learner_id}'
    job=db.scalar(select(Job).where(Job.learner_id==learner_id,Job.idempotency_key==key))
    if job:
        # Serialize requests against the worker's final pending-folder check.
        # A no-op write also obtains SQLite's write lock (FOR UPDATE is ignored).
        db.execute(update(Job).where(Job.id==job.id).values(id=Job.id))
        db.refresh(job)
    if job and job.state in {'succeeded','failed','needs-attention','cancelled'}:
        job.state='queued'; job.error_code=None; job.attempts=0; job.run_at=utcnow(); job.payload={}; job.lease_owner=None; job.lease_until=None
    if not job: job=enqueue(db,learner_id,'drive-provision',{},idempotency_key=key)
    if collection_id:
        collection=owned(db,Collection,collection_id,learner_id)
        collection.provisioning_job_id=job.id; collection.provisioning_state='pending'
    db.flush(); return job


def persist_snapshot(db, revision, snapshot, demo_fixture=False):
    if db.scalar(select(Chunk.id).where(Chunk.material_revision_id==revision.id)):
        owned(db,Material,revision.material_id,revision.learner_id).status='ready'
        return # Crash/replay cannot create another outline.
    for position,section in enumerate(snapshot.sections):
        text=section.text.strip()
        if not text: continue
        chunk=Chunk(learner_id=revision.learner_id,material_revision_id=revision.id,title=section.title[:500],position=position,source_locator_json=section.locator,text=text)
        db.add(chunk); db.flush()
        section_citation_id=str(uuid5(NAMESPACE_URL,f'learningos:{revision.id}:{position}'))
        db.add(Citation(id=section_citation_id,learner_id=revision.learner_id,revision_id=revision.id,locator_kind=section.locator_kind,locator_json=section.locator,excerpt=text,excerpt_hash=hashlib.sha256(text.encode()).hexdigest()))
        # Verbatim concepts: preserve every sentence, grouping long sections to bounded count.
        concept_text=re.sub(r'^#{1,6}\s+.*$', lambda match:' '*len(match.group()), text, flags=re.MULTILINE) if revision.metadata_json.get('filename','').endswith('.md') else text
        spans=[]
        for match in re.finditer(r'.+?(?:[.!?。！？](?=\s|$)|\n|$)',concept_text,re.DOTALL):
            part=match.group()
            if part.strip():spans.append((match.start()+len(part)-len(part.lstrip()),match.end()-len(part)+len(part.rstrip())))
        group_size=max(1,math.ceil(len(spans)/8))
        for index,start in enumerate(range(0,len(spans),group_size)):
            selected=spans[start:start+group_size]; excerpt_start,excerpt_end=selected[0][0],selected[-1][1]
            excerpt=text[excerpt_start:excerpt_end]
            citation=Citation(learner_id=revision.learner_id,revision_id=revision.id,locator_kind=section.locator_kind,locator_json={**section.locator,'concept_segment':index+1,'excerpt_start':excerpt_start,'excerpt_end':excerpt_end},excerpt=excerpt,excerpt_hash=hashlib.sha256(excerpt.encode()).hexdigest())
            db.add(citation); db.flush()
            db.add(Concept(learner_id=revision.learner_id,chunk_id=chunk.id,text=excerpt,citation_ids=[citation.id],critical=True,position=index,extraction_version=EXTRACTION_VERSION))
    revision.extracted_text='\n\n'.join(section.text for section in snapshot.sections)
    # Extraction may have waited on a provider after committing its checkpoint.
    # Refresh under lock so a concurrent learner correction cannot be overwritten
    # by this worker's expire_on_commit=False identity cache. No provider IO here.
    db.refresh(revision, ["source_language", "metadata_json"], with_for_update=True)
    if revision.metadata_json.get("source_language_provenance") != "learner":
        revision.source_language=snapshot.source_language
    revision.extraction_version=EXTRACTION_VERSION
    revision.metadata_json={**revision.metadata_json,**snapshot.metadata,'sections':len(snapshot.sections),'demo_fixture':demo_fixture or revision.metadata_json.get('demo_fixture',False)}
    if snapshot.canonical_url: revision.source_url=snapshot.canonical_url
    material=owned(db,Material,revision.material_id,revision.learner_id)
    material.current_revision_id=revision.id; material.status='ready'; material.version+=1
    db.flush()


def serialize_snapshot(snapshot, revision):
    kind=snapshot.sections[0].locator_kind
    segments=[]
    for index,section in enumerate(snapshot.sections):
        segment={'text':section.text,'citation_id':str(uuid5(NAMESPACE_URL,f'learningos:{revision.id}:{index}'))}
        if kind=='web':segment['paragraph']=section.locator['paragraph']
        else:segment.update(start_seconds=section.locator['start_seconds'],end_seconds=section.locator['end_seconds'])
        segments.append(segment)
    value={'schema_version':1,'kind':kind,'collection_id':revision.collection_id,'material_revision_id':revision.id,'canonical_url':snapshot.canonical_url,'captured_at':snapshot.metadata.get('snapshot_at') or utcnow().isoformat(),'source_language':snapshot.source_language,'segments':segments}
    jsonschema.validate(value,json.loads((Path(__file__).resolve().parents[2]/'contracts/link-source.schema.json').read_text()))
    return value


def parse_descriptor(data, learner_id, collection_id):
    # The Collection and revision are resolved against this learner by the caller;
    # untrusted descriptors never supply credentials or execute their URLs.
    try:
        value=json.loads(data)
        jsonschema.validate(value,json.loads((Path(__file__).resolve().parents[2]/'contracts/link-source.schema.json').read_text()))
        if value['collection_id']!=collection_id or len(value['segments'])>10000:raise ValueError()
        sections=[]
        for index,segment in enumerate(value['segments']):
            if segment['citation_id']!=str(uuid5(NAMESPACE_URL,f"learningos:{value['material_revision_id']}:{index}")):raise ValueError()
            if value['kind']=='web':
                locator={'url':value['canonical_url'],'snapshot_at':value['captured_at'],'paragraph':segment['paragraph']}
            else:
                from .sources.captions import video_id
                if segment['end_seconds']<=segment['start_seconds']:raise ValueError()
                locator={'video_id':video_id(value['canonical_url']),'url':value['canonical_url'],'start_seconds':segment['start_seconds'],'end_seconds':segment['end_seconds'],'language':value['source_language']}
            sections.append(ExtractedSection('Public source' if value['kind']=='web' else f'Caption {index+1}',segment['text'],value['kind'],locator))
        return value,SourceSnapshot(sections,value['canonical_url'],value['source_language'],{'snapshot_at':value['captured_at']})
    except (ValueError,KeyError,TypeError,jsonschema.ValidationError) as exc:
        raise SourceError('invalid_descriptor','The managed source descriptor does not match this owned Collection.') from exc


def save_to_drive(db, revision, data, filename, mime, job=None):
    collection=owned(db,Collection,revision.collection_id,revision.learner_id)
    if collection.storage_mode!='drive':
        revision.storage_state='local-only'; return
    if collection.provisioning_state!='ready' or not collection.drive_folder_id:
        queue_provision(db,revision.learner_id,collection.id); db.commit()
        raise SourceError('folder_pending','The Collection folder is still provisioning.',True)
    identity=f'upload:{revision.id}'
    receipt=db.scalar(select(SourceWriteReceipt).where(SourceWriteReceipt.learner_id==revision.learner_id,SourceWriteReceipt.collection_id==collection.id,SourceWriteReceipt.stable_identity==identity))
    if not receipt:
        receipt=SourceWriteReceipt(learner_id=revision.learner_id,collection_id=collection.id,material_id=revision.material_id,stable_identity=identity,folder_id=collection.drive_folder_id,origin=revision.origin)
        db.add(receipt); db.flush()
    if receipt.folder_id != collection.drive_folder_id: raise SourceError('folder_changed','The Collection folder changed; reconcile this pending write.')
    revision.storage_state='uploading'; receipt.stage='uploading'; db.commit()
    adapter=drive_adapter(db,revision.learner_id)
    def save_session(value): receipt.receipt_json=value; db.commit()
    db.commit()
    result=adapter.upload(collection.drive_folder_id,identity,filename,data,mime,receipt.receipt_json,save_session)
    if job and job.lease_owner is not None:assert_lease(db,job)
    if db.scalar(select(ProviderConnection.status).where(ProviderConnection.learner_id==revision.learner_id,ProviderConnection.provider=='drive'))!='connected':raise SourceError('drive_disconnected','Drive was disconnected; this receipt requires reconciliation.')
    if collection.drive_folder_id not in result.get('parents',[]): raise SourceError('drive_wrong_parent','Drive did not confirm the bound Collection folder.')
    revision.drive_file_id=result['id']; revision.provider_revision=str(result.get('version') or result.get('md5Checksum') or '1')
    revision.storage_state='saved-to-drive'; revision.storage_receipt={'file_id':result['id'],'folder_id':collection.drive_folder_id,'provider_revision':revision.provider_revision}
    receipt.drive_file_id=result['id']; receipt.provider_revision=revision.provider_revision; receipt.stage='confirmed'; receipt.checked_at=utcnow(); receipt.receipt_json=revision.storage_receipt
    db.commit()


def ingest_material(db,job):
    revision=owned(db,MaterialRevision,job.payload['revision_id'],job.learner_id)
    material=owned(db,Material,revision.material_id,job.learner_id)
    if material.current_revision_id==revision.id and material.status=='ready' and not job.payload.get('mirror'): return {'material_id':material.id,'revision_id':revision.id,'status':'ready'}
    material.status='processing'; db.commit()
    try:
        if revision.source_url and revision.origin=='ui_link':
            from urllib.parse import urlsplit
            host=urlsplit(revision.source_url).hostname
            if revision.private_blob_key:
                data=get_storage().get(job.learner_id,revision.private_blob_key)
                value,snapshot=parse_descriptor(data,job.learner_id,revision.collection_id)
                if value['material_revision_id']!=revision.id:raise SourceError('descriptor_binding','Source snapshot does not match its revision.')
            else:
                snapshot=extract_captions(revision.source_url) if host in {'youtube.com','www.youtube.com','m.youtube.com','youtu.be','www.youtu.be'} else fetch_public_page(revision.source_url)
                descriptor=serialize_snapshot(snapshot,revision)
                revision.metadata_json={**revision.metadata_json,'section_titles':[section.title for section in snapshot.sections]}
                data=json.dumps(descriptor,ensure_ascii=False).encode()
                reserve_source_quota(db,job.learner_id,revision.collection_id,len(data),revision_id=revision.id)
                revision.content_hash=hashlib.sha256(data).hexdigest(); revision.size=len(data); db.commit()
                revision.private_blob_key=get_storage().put(job.learner_id,data)
                db.commit()
            titles=revision.metadata_json.get('section_titles',[])
            if len(titles)==len(snapshot.sections):snapshot=SourceSnapshot([ExtractedSection(title,section.text,section.locator_kind,section.locator) for title,section in zip(titles,snapshot.sections)],snapshot.canonical_url,snapshot.source_language,snapshot.metadata)
            save_to_drive(db,revision,data,f'{material.id}.learningos-source.json','application/json',job)
        else:
            data=get_storage().get(job.learner_id,revision.private_blob_key)
            filename=revision.metadata_json.get('filename',material.title)
            if revision.origin=='direct_drop' and filename.endswith('.learningos-source.json'):
                _,snapshot=parse_descriptor(data,job.learner_id,revision.collection_id)
            else:
                from .llm import get_provider
                snapshot=extract_file(data,filename,revision.mime,vision=get_provider().vision)
            if revision.origin=='ui_upload': save_to_drive(db,revision,data,filename,revision.mime,job)
        if job.lease_owner is not None:assert_lease(db,job)
        persist_snapshot(db,revision,snapshot)
        return {'material_id':material.id,'revision_id':revision.id,'status':'ready','storage_state':revision.storage_state}
    except SourceError as exc:
        material.status='queued' if exc.retryable else 'needs-attention'
        revision.metadata_json={**revision.metadata_json,'error_code':exc.code,'error_message':exc.message}
        if exc.code.startswith('drive_') and not exc.retryable: revision.storage_state='attention'
        db.commit(); raise


def provision_drive(db,job):
    connection=connection_for(db,job.learner_id); adapter=drive_adapter(db,job.learner_id)
    db.commit()
    root=adapter.ensure_folder(f'root:{job.learner_id}','Learning OS',existing_id=connection.app_root_id)
    if job.lease_owner is not None:assert_lease(db,job)
    connection.app_root_id=root['id']; db.commit()
    collections=db.scalars(select(Collection).where(Collection.learner_id==job.learner_id,Collection.storage_mode=='drive',Collection.archived==False)).all()
    processed=set()
    while True:
        for collection in collections:
            try:
                collection.provisioning_state='provisioning'; db.commit()
                folder=adapter.ensure_folder(f'collection:{collection.id}',collection.name,root['id'],collection.drive_folder_id)
                if job.lease_owner is not None:assert_lease(db,job)
                collection.drive_folder_id=folder['id']; collection.drive_root_id=root['id']; collection.provisioning_state='ready'
                pending=db.scalar(select(Job).where(Job.learner_id==job.learner_id,Job.kind=='drive-sync',Job.entity_id==collection.id,Job.state.in_(['queued','running'])))
                if not pending: enqueue(db,job.learner_id,'drive-sync',{'collection_id':collection.id},idempotency_key=f'initial-poll:{collection.id}:{job.id}:{job.attempts}')
                db.commit(); processed.add(collection.id)
            except SourceError:
                collection.provisioning_state='needs-attention'; db.commit(); raise
        # Hold the same admission lock until run_once commits success. A request
        # that arrives later then observes succeeded and requeues this job;
        # one admitted during provider I/O is included in this next pass.
        db.execute(update(Job).where(Job.id==job.id).values(id=Job.id))
        if job.lease_owner is not None:assert_lease(db,job)
        collections=db.scalars(select(Collection).where(Collection.learner_id==job.learner_id,Collection.storage_mode=='drive',Collection.archived==False,
            (Collection.provisioning_state.in_(['pending','provisioning'])) | Collection.drive_folder_id.is_(None))).all()
        if not collections:
            break
    return {'root_id':root['id'],'collection_count':len(processed)}


def sync_drive(db,job):
    collection=owned(db,Collection,job.payload['collection_id'],job.learner_id)
    if collection.storage_mode!='drive' or collection.provisioning_state!='ready' or not collection.drive_folder_id:
        raise SourceError('folder_pending','Connect and provision this Collection first.',True)
    adapter=drive_adapter(db,job.learner_id)
    db.commit()
    folder=adapter.get_file(collection.drive_folder_id)
    if folder.get('trashed') or collection.drive_root_id not in folder.get('parents',[]):
        collection.provisioning_state='needs-attention'; db.commit(); raise SourceError('drive_folder_missing','The folder was moved/deleted; explicitly relink it.')
    files=adapter.list_files(collection.drive_folder_id); discovered=0; seen=set()
    for remote in files:
        identifier=remote['id']; seen.add(identifier)
        version=str(remote.get('version') or remote.get('md5Checksum') or '1')
        existing=db.scalar(select(MaterialRevision).where(MaterialRevision.learner_id==job.learner_id,MaterialRevision.collection_id==collection.id,MaterialRevision.drive_file_id==identifier,MaterialRevision.provider_revision==version))
        if existing:
            if not existing.private_blob_key:
                db.commit()
                recovered=adapter.download(identifier,settings.max_upload_bytes)
                reserve_source_quota(db,job.learner_id,collection.id,len(recovered),revision_id=existing.id)
                existing.size=len(recovered);db.commit()
                existing.private_blob_key=get_storage().put(job.learner_id,recovered)
                enqueue(db,job.learner_id,'ingest-material',{'revision_id':existing.id},idempotency_key=f'ingest:{existing.id}');db.commit()
            continue
        filename=remote['name']; suffix=Path(filename).suffix.lower(); descriptor=filename.endswith('.learningos-source.json')
        if suffix not in SUPPORTED and not descriptor: continue
        if int(remote.get('size',0))>settings.max_upload_bytes: continue
        db.commit()
        data=adapter.download(identifier,settings.max_upload_bytes)
        if job.lease_owner is not None:assert_lease(db,job)
        prior=db.scalar(select(MaterialRevision).where(MaterialRevision.learner_id==job.learner_id,MaterialRevision.collection_id==collection.id,MaterialRevision.drive_file_id==identifier).order_by(MaterialRevision.created_at.desc()))
        if descriptor:
            # Only app-origin typed descriptors reconcile existing links; arbitrary JSON never executes.
            if remote.get('appProperties',{}).get('learningos_schema')!='1': continue
            value,_=parse_descriptor(data,job.learner_id,collection.id)
            original=owned(db,MaterialRevision,value['material_revision_id'],job.learner_id)
            material=owned(db,Material,original.material_id,job.learner_id)
            if original.collection_id!=collection.id or original.material_id!=material.id or original.drive_file_id not in {None,identifier} or remote.get('appProperties',{}).get('learningos_identity')!=f'upload:{original.id}':
                raise SourceError('descriptor_binding','This source descriptor has an invalid material binding.')
            if original.drive_file_id is None:
                original.drive_file_id=identifier; original.provider_revision=version; original.storage_state='saved-to-drive'; db.commit(); continue
        elif prior:
            reserve_source_quota(db,job.learner_id,collection.id,len(data))
            material=owned(db,Material,prior.material_id,job.learner_id)
        else:
            reserve_source_quota(db,job.learner_id,collection.id,len(data),new_material=True)
            material=Material(learner_id=job.learner_id,collection_id=collection.id,title=filename,source_type='drive',status='queued',position=db.scalar(select(func.count(Material.id)).where(Material.collection_id==collection.id)) or 0)
            db.add(material); db.flush()
        if descriptor:reserve_source_quota(db,job.learner_id,collection.id,len(data))
        revision=MaterialRevision(learner_id=job.learner_id,collection_id=collection.id,material_id=material.id,content_hash=hashlib.sha256(data).hexdigest(),provider_revision=version,drive_file_id=identifier,origin='direct_drop',storage_state='saved-to-drive',private_blob_key=None,mime=remote.get('mimeType','application/octet-stream'),size=len(data),metadata_json={'filename':filename})
        db.add(revision); db.flush(); db.commit()
        revision.private_blob_key=get_storage().put(job.learner_id,data)
        enqueue(db,job.learner_id,'ingest-material',{'revision_id':revision.id},idempotency_key=f'ingest:{revision.id}'); discovered+=1; db.commit()
    revisions=db.scalars(select(MaterialRevision).where(MaterialRevision.learner_id==job.learner_id,MaterialRevision.collection_id==collection.id,MaterialRevision.drive_file_id.is_not(None))).all()
    for revision in revisions:
        if revision.drive_file_id not in seen:
            revision.metadata_json={**revision.metadata_json,'remote_state':'removed-or-moved','requires_reconciliation':True}
    collection.last_sync=utcnow(); connection=connection_for(db,job.learner_id); connection.last_sync=utcnow(); connection.checkpoint={**connection.checkpoint,collection.id:{'last_scan':utcnow().isoformat(),'file_count':len(files)}}
    # Durable bounded polling; disconnect cancels this before the next run.
    enqueue(db,job.learner_id,'drive-sync',{'collection_id':collection.id},idempotency_key=f'poll:{collection.id}:{job.id}',run_at=utcnow()+timedelta(seconds=60))
    return {'collection_id':collection.id,'discovered':discovered,'scanned':len(files)}

def job_handler(handler):
    def wrapped(db,job):
        try:return handler(db,job)
        except SourceError as exc:
            raise (RetryableJobError(exc.code) if exc.retryable else NeedsAttention(exc.code)) from exc
    return wrapped

register('ingest-material',job_handler(ingest_material))
register('drive-provision',job_handler(provision_drive))
register('drive-sync',job_handler(sync_drive))
