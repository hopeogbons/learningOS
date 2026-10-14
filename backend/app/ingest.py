"""One immutable pipeline for local, UI-to-Drive, links and direct folder drops."""
import hashlib
import json
import os
from uuid import uuid5, NAMESPACE_URL
import jsonschema
from datetime import timedelta
from pathlib import Path
from sqlalchemy import select, func, update, delete
from .models import (Learner, Collection, Material, MaterialRevision, Chunk, Concept, Citation,
                     ProviderConnection, SourceWriteReceipt, Job, ScopeRevision, ScopeItem,
                     TitleAssessment, StudySession, SessionItem, ProgressEvent, ReviewState,
                     ConceptRelation, OutboxEvent, Notification)
from .db import utcnow
from .jobs import enqueue, register, NeedsAttention, RetryableJobError, LostLease, assert_lease
from .storage import get_storage
from .settings import settings
from .sources.base import SourceError, SourceSnapshot, ExtractedSection
from .sources.local import (extract_file, split_teaching_windows, SUPPORTED,
                            pdf_manifest_info, extract_pdf_page_batch,
                            merge_pdf_bookmark_sections)
from .ingest_limits import (PDF_BATCH_PAGES, MAX_PDF_EXTRACTED_BYTES,
                            MAX_TEACHING_WINDOWS, MAX_UPLOAD_BYTES)
from .sources.publicweb import fetch_public_page
from .sources.captions import extract_captions
from .sources.drive import DriveAdapter, decrypt_credentials, encrypt_credentials, READ_SCOPE, WRITE_SCOPE

EXTRACTION_VERSION = 'source-excerpts-v3'
INGESTION_JOB_KINDS = ('ingest-material','ingest-pdf-batch','ingest-pdf-finalize')


def owned(db, model, identifier, learner_id):
    value=db.scalar(select(model).where(model.id==identifier,model.learner_id==learner_id))
    if not value: raise SourceError('not_found','The requested source is unavailable.')
    return value


def reserve_source_quota(db,learner_id,collection_id,size,revision_id=None,new_material=False):
    """Serialize tenant reservations before inserting/updating revision.size.

    Caller persists its reservation in the same transaction before blob/network work.
    Existing revision bytes are replaced, not double-counted on retry.
    """
    max_upload_bytes=min(settings.max_upload_bytes,MAX_UPLOAD_BYTES)
    if size<0 or size>max_upload_bytes:raise SourceError('oversize','The source exceeds the upload limit.')
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
    prepared=[]
    window_total=0
    for section in snapshot.sections:
        raw_text=section.text
        text=raw_text.strip()
        if not text: continue
        trim_start=len(raw_text)-len(raw_text.lstrip())
        locator=dict(section.locator)
        if locator.get('section_char_start') is not None:
            locator['section_char_start']=int(locator['section_char_start'])+trim_start
            locator['section_char_end']=int(locator['section_char_start'])+len(text)
        if locator.get('line_start') is not None:
            removed_lines=raw_text[:trim_start].count('\n')
            locator['line_start']=int(locator['line_start'])+removed_lines
            locator['line_end']=int(locator['line_start'])+text.count('\n')
        windows=split_teaching_windows(text)
        window_total+=len(windows)
        if window_total>MAX_TEACHING_WINDOWS:
            raise SourceError('teaching_window_limit','This source creates too many bounded teaching units. Split it into smaller files.')
        prepared.append((section,text,windows,locator))
    for position,(section,text,windows,section_locator) in enumerate(prepared):
        chunk=Chunk(learner_id=revision.learner_id,material_revision_id=revision.id,title=section.title[:500],position=position,source_locator_json=section_locator,text=text)
        db.add(chunk); db.flush()
        section_citation_id=str(uuid5(NAMESPACE_URL,f'learningos:{revision.id}:{position}'))
        db.add(Citation(id=section_citation_id,learner_id=revision.learner_id,revision_id=revision.id,locator_kind=section.locator_kind,locator_json=section_locator,excerpt=text,excerpt_hash=hashlib.sha256(text.encode()).hexdigest()))
        for index,window in enumerate(windows):
            excerpt_start=int(window['start']);excerpt_end=int(window['end'])
            core_start=int(window['core_start']);core_end=int(window['core_end'])
            excerpt=str(window['text']);core=str(window['core_text'])
            teaching_prefix=str(section.locator.get('key_path') or '').strip()
            concept_text=f'{teaching_prefix}: {core}' if teaching_prefix else core
            locator={**section_locator,'concept_segment':index+1,'excerpt_start':excerpt_start,'excerpt_end':excerpt_end,'core_excerpt_start':core_start,'core_excerpt_end':core_end}
            base_start=int(section_locator.get('section_char_start',0))
            locator['section_char_start']=base_start+excerpt_start
            locator['section_char_end']=base_start+excerpt_end
            if section.locator_kind=='text' and section_locator.get('line_start'):
                locator['line_start']=int(section_locator['line_start'])+text[:excerpt_start].count('\n')
                locator['line_end']=int(section_locator['line_start'])+text[:excerpt_end].count('\n')
            citation=Citation(learner_id=revision.learner_id,revision_id=revision.id,locator_kind=section.locator_kind,locator_json=locator,excerpt=excerpt,excerpt_hash=hashlib.sha256(excerpt.encode()).hexdigest())
            db.add(citation); db.flush()
            db.add(Concept(learner_id=revision.learner_id,chunk_id=chunk.id,text=concept_text,citation_ids=[citation.id],critical=True,position=index,extraction_version=EXTRACTION_VERSION))
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
    material=owned(db,Material,revision.material_id,revision.learner_id)
    db.refresh(material,['status','archived'])
    if material.archived or material.status=='deleting':
        raise SourceError('material_deleting','This material is being deleted.')
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


def _new_pdf_manifest(info):
    page_count=info['page_count']
    pages=[{
        'page_number':number,
        'status':'pending',
        'method':None,
        'warning':None,
        'text_chars':0,
        'section_count':0,
        'chapter_path':info['chapter_paths'][number-1],
    } for number in range(1,page_count+1)]
    batches=[{
        'index':index,
        'start_page':start,
        'end_page':min(start+PDF_BATCH_PAGES-1,page_count),
        'state':'queued',
        'job_id':None,
        'result_blob_key':None,
        'result_bytes':0,
    } for index,start in enumerate(range(1,page_count+1,PDF_BATCH_PAGES))]
    return {
        'version':1,
        'status':'processing',
        'page_count':page_count,
        'batch_size':PDF_BATCH_PAGES,
        'processed_pages':0,
        'review_required_pages':[],
        'chapter_paths':info['chapter_paths'],
        'batches':batches,
        'batch_result_bytes':0,
        'extracted_text_bytes':0,
        'finalize_job_id':None,
    },pages


def _schedule_pdf_batch(db,revision,manifest,index):
    batch=manifest['batches'][index]
    key=f'pdf-batch:{revision.id}:{index}'
    job=enqueue(db,revision.learner_id,'ingest-pdf-batch',{
        'revision_id':revision.id,
        'material_id':revision.material_id,
        'collection_id':revision.collection_id,
        'batch_index':index,
    },idempotency_key=key)
    batch['job_id']=job.id
    batch['state']=job.state
    return job


def _schedule_pdf_finalize(db,revision,manifest):
    job=enqueue(db,revision.learner_id,'ingest-pdf-finalize',{
        'revision_id':revision.id,
        'material_id':revision.material_id,
        'collection_id':revision.collection_id,
    },idempotency_key=f'pdf-finalize:{revision.id}')
    manifest['finalize_job_id']=job.id
    manifest['status']='finalizing'
    return job


def _start_pdf_pipeline(db,revision,material,data,filename,job):
    manifest=revision.metadata_json.get('ingestion_manifest')
    if not manifest:
        manifest,pages=_new_pdf_manifest(pdf_manifest_info(data))
        manifest['pages']=pages
    else:
        manifest={**manifest,'batches':[dict(batch) for batch in manifest.get('batches',[])],
                  'pages':[dict(page) for page in manifest.get('pages',[])]}

    if manifest.get('status')=='ready':
        material.status='ready'
        return {'material_id':material.id,'revision_id':revision.id,'status':'ready'}
    if manifest.get('status')=='needs-review':
        material.status='needs-attention'
        revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest}
        db.commit()
        return {'material_id':material.id,'revision_id':revision.id,'status':'needs-attention'}

    next_batch=next((b for b in manifest['batches'] if b.get('state')!='completed'),None)
    if next_batch:
        _schedule_pdf_batch(db,revision,manifest,int(next_batch['index']))
        manifest['status']='processing'
    elif manifest.get('review_required_pages'):
        manifest['status']='needs-review'
        material.status='needs-attention'
    else:
        _schedule_pdf_finalize(db,revision,manifest)
        material.status='processing'
    revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest}
    db.commit()
    return {'material_id':material.id,'revision_id':revision.id,'status':material.status,
            'page_count':manifest['page_count'],'batch_size':PDF_BATCH_PAGES}


def ingest_material(db,job):
    revision=owned(db,MaterialRevision,job.payload['revision_id'],job.learner_id)
    material=owned(db,Material,revision.material_id,job.learner_id)
    db.refresh(material,['status','archived'])
    if material.archived or material.status=='deleting':
        return {'material_id':material.id,'revision_id':revision.id,'status':'cancelled'}
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
            if Path(filename).suffix.lower()=='.pdf':
                if revision.origin=='ui_upload':
                    save_to_drive(db,revision,data,filename,revision.mime,job)
                db.refresh(material,['status','archived'])
                if material.archived or material.status=='deleting':
                    return {'material_id':material.id,'revision_id':revision.id,'status':'cancelled'}
                return _start_pdf_pipeline(db,revision,material,data,filename,job)
            if revision.origin=='direct_drop' and filename.endswith('.learningos-source.json'):
                _,snapshot=parse_descriptor(data,job.learner_id,revision.collection_id)
            else:
                from .llm import get_provider
                snapshot=extract_file(data,filename,revision.mime,vision=get_provider().vision)
            if revision.origin=='ui_upload': save_to_drive(db,revision,data,filename,revision.mime,job)
        db.refresh(material,['status','archived'])
        if material.archived or material.status=='deleting':
            return {'material_id':material.id,'revision_id':revision.id,'status':'cancelled'}
        if job.lease_owner is not None:assert_lease(db,job)
        persist_snapshot(db,revision,snapshot)
        return {'material_id':material.id,'revision_id':revision.id,'status':'ready','storage_state':revision.storage_state}
    except SourceError as exc:
        db.refresh(material,['status','archived'])
        if not material.archived and material.status!='deleting':
            material.status='queued' if exc.retryable else 'needs-attention'
        revision.metadata_json={**revision.metadata_json,'error_code':exc.code,'error_message':exc.message}
        if exc.code.startswith('drive_') and not exc.retryable: revision.storage_state='attention'
        db.commit(); raise


def _section_json(section):
    return {'title':section.title,'text':section.text,'locator_kind':section.locator_kind,'locator':section.locator}


def _section_from_json(value):
    return ExtractedSection(value['title'],value['text'],value['locator_kind'],value['locator'])


def _manifest_review_pages(manifest):
    pages=manifest.get('pages',[])
    manifest['processed_pages']=sum(page.get('status')!='pending' for page in pages)
    manifest['review_required_pages']=[page['page_number'] for page in pages if page.get('status') in {'needs-review','failed'}]
    manifest['review_required_count']=len(manifest['review_required_pages'])


def ingest_pdf_batch(db,job):
    revision=owned(db,MaterialRevision,job.payload['revision_id'],job.learner_id)
    material=owned(db,Material,revision.material_id,job.learner_id)
    db.refresh(material,['status','archived'])
    if material.archived or material.status=='deleting':
        return {'material_id':material.id,'status':'cancelled'}
    db.refresh(revision,['metadata_json','private_blob_key'])
    manifest=dict(revision.metadata_json.get('ingestion_manifest') or {})
    batch_index=int(job.payload['batch_index'])
    batches=[dict(batch) for batch in manifest.get('batches',[])]
    if not 0<=batch_index<len(batches):
        raise NeedsAttention('pdf_batch_manifest_invalid')
    batch=batches[batch_index]
    if batch.get('state')=='completed':
        return {'material_id':material.id,'batch_index':batch_index,'status':'completed'}
    source=get_storage().get(job.learner_id,revision.private_blob_key)
    chapter_paths=list(manifest.get('chapter_paths',[]))

    def vision(image,mime):
        from .llm import get_provider
        return get_provider().vision(image,mime,revision.source_language)

    try:
        sections,page_results=extract_pdf_page_batch(
            source,
            revision.metadata_json.get('filename',material.title),
            int(batch['start_page']),
            int(batch['end_page']),
            chapter_paths,
            vision=vision,
        )
    except SourceError as exc:
        # Preserve accounting for the whole failed range; the learner can review
        # and correct individual pages rather than seeing a false partial success.
        page_status='failed' if exc.code in {'unreadable_pdf','pdf_batch_range'} else 'needs-review'
        page_results=[{
            'page_number':number,'status':page_status,'method':None,
            'warning':exc.code,'text_chars':0,'section_count':0,
            'chapter_path':chapter_paths[number-1] if number<=len(chapter_paths) else [],
        } for number in range(int(batch['start_page']),int(batch['end_page'])+1)]
        sections=[]

    current_result={'revision_id':revision.id,'batch_index':batch_index,
                    'sections':[_section_json(section) for section in sections],
                    'page_results':page_results}
    result_bytes=json.dumps(current_result,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    previous_text_bytes=int(batch.get('extracted_text_bytes',0))
    previous_result_bytes=int(batch.get('result_bytes',0))
    batch_text_bytes=sum(len(section.text.encode('utf-8')) for section in sections)
    total_text_bytes=int(manifest.get('extracted_text_bytes',0))-previous_text_bytes+batch_text_bytes
    if total_text_bytes>MAX_PDF_EXTRACTED_BYTES:
        sections=[]
        page_results=[{**page,'status':'needs-review','warning':'extracted_text_limit','text_chars':0,'section_count':0} for page in page_results]
        batch_text_bytes=0
        total_text_bytes=int(manifest.get('extracted_text_bytes',0))-previous_text_bytes
        current_result={'revision_id':revision.id,'batch_index':batch_index,'sections':[],'page_results':page_results}
        result_bytes=json.dumps(current_result,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    result_key=get_storage().put(job.learner_id,result_bytes,f'{material.id}-pages-{batch_index}.json')

    manifest['pages']=[dict(page) for page in manifest.get('pages',[])]
    by_page={page['page_number']:page for page in page_results}
    for page in manifest['pages']:
        if page['page_number'] in by_page:
            page.update(by_page[page['page_number']])
    manifest['batches']=batches
    batch.update(state='completed',result_blob_key=result_key,result_bytes=len(result_bytes),
                 extracted_text_bytes=batch_text_bytes,job_id=job.id)
    manifest['batch_result_bytes']=int(manifest.get('batch_result_bytes',0))-previous_result_bytes+len(result_bytes)
    manifest['extracted_text_bytes']=total_text_bytes
    _manifest_review_pages(manifest)

    next_batch=next((item for item in batches if item.get('state')!='completed'),None)
    if next_batch:
        _schedule_pdf_batch(db,revision,manifest,int(next_batch['index']))
        manifest['status']='processing'
        material.status='processing'
    elif manifest['review_required_count']:
        manifest['status']='needs-review'
        material.status='needs-attention'
    else:
        _schedule_pdf_finalize(db,revision,manifest)
        material.status='processing'
    revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest}
    db.commit()
    if job.lease_owner is not None:
        assert_lease(db,job)
    return {'material_id':material.id,'batch_index':batch_index,'page_count':manifest['page_count'],
            'processed_pages':manifest['processed_pages'],'review_required_count':manifest['review_required_count'],
            'status':manifest['status']}


def _purge_pdf_batch_results(db,job,learner_id):
    payload=dict(job.payload or {})
    keys=list(payload.get('temporary_result_keys',[]))
    deleted=set(payload.get('deleted_result_keys',[]))
    storage=get_storage()
    for key in keys:
        if key in deleted:
            continue
        try:
            storage.delete(learner_id,key)
        except Exception as exc:
            raise RetryableJobError('pdf_batch_cleanup_failed') from exc
        deleted.add(key)
        payload['deleted_result_keys']=sorted(deleted)
        job.payload=payload
        db.commit()
        if job.lease_owner is not None:
            assert_lease(db,job)
    job.payload={}
    job.entity_id=None
    job.idempotency_key=None
    db.commit()
    return {'status':'ready','batch_results_cleaned':len(keys)}


def finalize_pdf_material(db,job):
    if job.payload.get('finalized'):
        return _purge_pdf_batch_results(db,job,job.learner_id)
    revision=owned(db,MaterialRevision,job.payload['revision_id'],job.learner_id)
    material=owned(db,Material,job.payload['material_id'],job.learner_id)
    db.refresh(revision,['metadata_json'])
    manifest=dict(revision.metadata_json.get('ingestion_manifest') or {})
    _manifest_review_pages(manifest)
    if manifest.get('review_required_count'):
        manifest['status']='needs-review';material.status='needs-attention'
        revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest};db.commit()
        raise NeedsAttention('pdf_pages_need_review')
    if any(batch.get('state')!='completed' for batch in manifest.get('batches',[])):
        raise RetryableJobError('pdf_batches_incomplete')

    storage=get_storage()
    sections=[]
    temporary_keys=[]
    extracted_bytes=0
    for batch in manifest.get('batches',[]):
        key=batch.get('result_blob_key')
        if not key:
            raise NeedsAttention('pdf_batch_result_missing')
        temporary_keys.append(key)
        data=storage.get(job.learner_id,key)
        extracted_bytes+=sum(len(str(section.get('text','')).encode('utf-8')) for section in json.loads(data).get('sections',[]))
        if extracted_bytes>MAX_PDF_EXTRACTED_BYTES:
            raise NeedsAttention('pdf_extracted_text_limit')
        value=json.loads(data)
        if value.get('revision_id')!=revision.id or value.get('batch_index')!=batch.get('index'):
            raise NeedsAttention('pdf_batch_binding_invalid')
        sections.extend(_section_from_json(section) for section in value.get('sections',[]))
    temporary_keys.extend(manifest.get('obsolete_result_blob_keys',[]))
    sections=merge_pdf_bookmark_sections(sections)
    if not sections:
        raise NeedsAttention('empty_pdf_source')
    snapshot=SourceSnapshot(sections,source_language=revision.source_language,
                            metadata={'pdf_page_count':manifest['page_count'],'pdf_batch_size':manifest['batch_size']})
    persist_snapshot(db,revision,snapshot)
    manifest['status']='ready'
    manifest['processed_pages']=manifest['page_count']
    manifest['obsolete_result_blob_keys']=[]
    for batch in manifest.get('batches',[]):
        batch.pop('result_blob_key',None)
    revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest}
    job.payload={'finalized':True,'temporary_result_keys':temporary_keys,'deleted_result_keys':[]}
    db.commit()
    if job.lease_owner is not None:
        assert_lease(db,job)
    return _purge_pdf_batch_results(db,job,job.learner_id)


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


def _record_direct_drop_attention(db,job,collection,remote,version,prior,code):
    """Persist visible attention for a Drive drop rejected by bounded intake."""
    filename=remote.get('name') or 'Drive source'
    identifier=remote['id']
    if prior:
        material=owned(db,Material,prior.material_id,job.learner_id)
        reserve_source_quota(db,job.learner_id,collection.id,0,revision_id=prior.id)
    else:
        reserve_source_quota(db,job.learner_id,collection.id,0,new_material=True)
        material=Material(
            learner_id=job.learner_id,collection_id=collection.id,title=filename,
            source_type=Path(filename).suffix.lower().lstrip('.') or 'drive',
            status='needs-attention',
            position=db.scalar(select(func.count(Material.id)).where(
                Material.collection_id==collection.id,
                Material.learner_id==job.learner_id,
            )) or 0,
        )
        db.add(material);db.flush()
    metadata={
        'filename':filename,'direct_drop_rejected':True,'error_code':code,
        'reported_size':max(0,int(remote.get('size') or 0)),
        'reported_mime':remote.get('mimeType','application/octet-stream'),
    }
    revision=MaterialRevision(
        learner_id=job.learner_id,collection_id=collection.id,material_id=material.id,
        content_hash=hashlib.sha256(f'{identifier}:{version}:{code}'.encode()).hexdigest(),
        provider_revision=version,drive_file_id=identifier,origin='direct_drop',
        storage_state='saved-to-drive',private_blob_key=None,
        mime=remote.get('mimeType','application/octet-stream'),size=0,
        metadata_json=metadata,
    )
    db.add(revision);db.flush()
    material.current_revision_id=revision.id
    material.status='needs-attention'
    return revision


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
            existing_material=owned(db,Material,existing.material_id,job.learner_id)
            db.refresh(existing_material,['status','archived'])
            if existing_material.archived or existing_material.status=='deleting':
                continue
            if existing.metadata_json.get('direct_drop_rejected'):
                continue
            if not existing.private_blob_key:
                db.commit()
                recovered=adapter.download(identifier,min(settings.max_upload_bytes,MAX_UPLOAD_BYTES))
                reserve_source_quota(db,job.learner_id,collection.id,len(recovered),revision_id=existing.id)
                existing.size=len(recovered);db.commit()
                existing.private_blob_key=get_storage().put(job.learner_id,recovered)
                enqueue(db,job.learner_id,'ingest-material',{'revision_id':existing.id},idempotency_key=f'ingest:{existing.id}');db.commit()
            continue
        filename=remote['name']; suffix=Path(filename).suffix.lower(); descriptor=filename.endswith('.learningos-source.json')
        prior=db.scalar(select(MaterialRevision).where(
            MaterialRevision.learner_id==job.learner_id,
            MaterialRevision.collection_id==collection.id,
            MaterialRevision.drive_file_id==identifier,
        ).order_by(MaterialRevision.created_at.desc()))
        if suffix not in SUPPORTED and not descriptor:
            _record_direct_drop_attention(db,job,collection,remote,version,prior,'unsupported_type')
            discovered+=1;db.commit();continue
        upload_limit=min(settings.max_upload_bytes,MAX_UPLOAD_BYTES)
        if int(remote.get('size',0))>upload_limit:
            _record_direct_drop_attention(db,job,collection,remote,version,prior,'oversize')
            discovered+=1;db.commit();continue
        db.commit()
        try:
            data=adapter.download(identifier,upload_limit)
        except SourceError as exc:
            if exc.code!='oversize':raise
            _record_direct_drop_attention(db,job,collection,remote,version,prior,'oversize')
            discovered+=1;db.commit();continue
        if job.lease_owner is not None:assert_lease(db,job)
        prior=db.scalar(select(MaterialRevision).where(MaterialRevision.learner_id==job.learner_id,MaterialRevision.collection_id==collection.id,MaterialRevision.drive_file_id==identifier).order_by(MaterialRevision.created_at.desc()))
        file_source_type='photo' if suffix in {'.png','.jpg','.jpeg'} else suffix.lstrip('.') or 'drive'
        if descriptor:
            # Only app-origin typed descriptors reconcile existing links; arbitrary JSON never executes.
            if remote.get('appProperties',{}).get('learningos_schema')!='1': continue
            value,_=parse_descriptor(data,job.learner_id,collection.id)
            original=owned(db,MaterialRevision,value['material_revision_id'],job.learner_id)
            material=owned(db,Material,original.material_id,job.learner_id)
            db.refresh(material,['status','archived'])
            if material.archived or material.status=='deleting':
                continue
            if original.collection_id!=collection.id or original.material_id!=material.id or original.drive_file_id not in {None,identifier} or remote.get('appProperties',{}).get('learningos_identity')!=f'upload:{original.id}':
                raise SourceError('descriptor_binding','This source descriptor has an invalid material binding.')
            if original.drive_file_id is None:
                original.drive_file_id=identifier; original.provider_revision=version; original.storage_state='saved-to-drive'; db.commit(); continue
        elif prior:
            reserve_source_quota(db,job.learner_id,collection.id,len(data))
            material=owned(db,Material,prior.material_id,job.learner_id)
            db.refresh(material,['status','archived'])
            if material.archived or material.status=='deleting':
                continue
            material.source_type=file_source_type
        else:
            reserve_source_quota(db,job.learner_id,collection.id,len(data),new_material=True)
            material=Material(learner_id=job.learner_id,collection_id=collection.id,title=filename,source_type=file_source_type,status='queued',position=db.scalar(select(func.count(Material.id)).where(Material.collection_id==collection.id)) or 0)
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


def delete_material(db,job):
    """Purge one Material only after every bound remote original is confirmed deleted."""
    payload=dict(job.payload or {})
    learner_id=job.learner_id

    def purge_private_blobs():
        storage=get_storage()
        completed=set(payload.get('private_deleted_keys',[]))
        for key in payload.get('private_blob_keys',[]):
            if key in completed:
                continue
            references=select(MaterialRevision.id).where(
                MaterialRevision.learner_id==learner_id,
                MaterialRevision.private_blob_key==key,
            )
            target_revision_ids=payload.get('revision_ids',[])
            if target_revision_ids:
                references=references.where(MaterialRevision.id.not_in(target_revision_ids))
            still_referenced=db.scalar(references.limit(1))
            if not still_referenced:
                try:
                    storage.delete(learner_id,key)
                except Exception as exc:
                    raise RetryableJobError('material_blob_delete_failed') from exc
            completed.add(key)
            payload['private_deleted_keys']=sorted(completed)
            job.payload=payload
            db.commit()
            assert_lease(db,job)

    if payload.get('database_deleted'):
        purge_private_blobs()
        job.payload={}
        job.entity_id=None
        job.idempotency_key=None
        db.commit()
        return {'deleted':True}

    material=owned(db,Material,payload.get('material_id',''),learner_id)
    collection=owned(db,Collection,payload.get('collection_id',''),learner_id)
    if material.collection_id!=collection.id:
        raise NeedsAttention('material_collection_mismatch')
    db.refresh(material,['status','archived'])
    if material.archived:
        raise NeedsAttention('material_already_archived')
    material.status='deleting'

    revisions=db.scalars(select(MaterialRevision).where(
        MaterialRevision.learner_id==learner_id,
        MaterialRevision.material_id==material.id,
        MaterialRevision.collection_id==collection.id,
    )).all()
    revision_ids={revision.id for revision in revisions}
    chunk_ids=set(db.scalars(select(Chunk.id).where(
        Chunk.learner_id==learner_id,
        Chunk.material_revision_id.in_(revision_ids),
    )).all()) if revision_ids else set()
    affected_scope_ids=set(db.scalars(select(ScopeItem.scope_revision_id).where(
        ScopeItem.learner_id==learner_id,
        ScopeItem.chunk_id.in_(chunk_ids),
    )).all()) if chunk_ids else set()
    session_ids=set(db.scalars(select(StudySession.id).where(
        StudySession.learner_id==learner_id,
        StudySession.scope_revision_id.in_(affected_scope_ids),
    )).all()) if affected_scope_ids else set()
    if chunk_ids:
        session_ids.update(db.scalars(select(SessionItem.session_id).where(
            SessionItem.learner_id==learner_id,
            SessionItem.chunk_id.in_(chunk_ids),
        )).all())

    # Wait for extraction work already in flight. Queued work is cancelled only
    # after remote deletion is confirmed, so a failed Drive delete changes no history.
    active_ingests=db.scalars(select(Job).where(
        Job.learner_id==learner_id,
        Job.kind.in_(INGESTION_JOB_KINDS),
        Job.state=='running',
    )).all()
    if any(candidate.payload.get('revision_id') in revision_ids for candidate in active_ingests):
        raise RetryableJobError('material_ingestion_in_flight')

    session_jobs=db.scalars(select(Job).where(
        Job.learner_id==learner_id,
        Job.entity_id.in_(session_ids) if session_ids else False,
        Job.kind.in_(['session.generate','session.assess','session.summary','session.finished']),
        Job.state=='running',
    )).all() if session_ids else []
    if session_jobs:
        raise RetryableJobError('material_session_in_flight')

    payload.setdefault('material_id',material.id)
    payload.setdefault('collection_id',collection.id)
    if not payload.get('deletion_plan_ready'):
        private_blob_keys={revision.private_blob_key for revision in revisions if revision.private_blob_key}
        for revision in revisions:
            manifest=revision.metadata_json.get('ingestion_manifest') or {}
            private_blob_keys.update(
                batch['result_blob_key'] for batch in manifest.get('batches',[])
                if batch.get('result_blob_key')
            )
            private_blob_keys.update(manifest.get('obsolete_result_blob_keys',[]))
        private_blob_keys=sorted(private_blob_keys)
        remote_ids={revision.drive_file_id for revision in revisions if revision.drive_file_id}
        receipts=db.scalars(select(SourceWriteReceipt).where(
            SourceWriteReceipt.learner_id==learner_id,
            SourceWriteReceipt.collection_id==collection.id,
            SourceWriteReceipt.material_id==material.id,
        )).all()
        remote_ids.update(receipt.drive_file_id for receipt in receipts if receipt.drive_file_id)

        could_have_remote=(
            bool(remote_ids)
            or bool(receipts)
            or any(revision.storage_state in {'uploading','saved-to-drive'} for revision in revisions)
        )
        if could_have_remote and (not collection.drive_folder_id or collection.provisioning_state!='ready'):
            raise SourceError('drive_folder_missing','The Collection Drive folder must be verified before deleting its source.',True)
        if collection.storage_mode=='drive' and collection.provisioning_state=='ready' and collection.drive_folder_id:
            adapter=drive_adapter(db,learner_id)
            folder=adapter.get_file(collection.drive_folder_id)
            if folder.get('trashed') or folder.get('mimeType')!='application/vnd.google-apps.folder' or (collection.drive_root_id and collection.drive_root_id not in folder.get('parents',[])):
                raise SourceError('drive_folder_missing','The bound Collection folder could not be verified before deletion.')
            for revision in revisions:
                if revision.origin in {'ui_upload','ui_link'}:
                    identity_files=adapter.list_files(collection.drive_folder_id,f'upload:{revision.id}')
                    remote_ids.update(file['id'] for file in identity_files)

        payload.update({
            'revision_ids':sorted(revision_ids),
            'private_blob_keys':private_blob_keys,
            'drive_folder_id':collection.drive_folder_id,
            'drive_file_ids':sorted(remote_ids),
            'drive_deleted_ids':[],
            'private_deleted_keys':[],
            'deletion_plan_ready':True,
        })
        job.payload=payload
        db.commit()
        assert_lease(db,job)

    drive_file_ids=set(payload.get('drive_file_ids',[]))
    deleted_drive_ids=set(payload.get('drive_deleted_ids',[]))
    if drive_file_ids:
        if not payload.get('drive_folder_id'):
            raise SourceError('drive_folder_missing','The bound Collection folder is unavailable; remote source deletion cannot be confirmed.')
        adapter=drive_adapter(db,learner_id)
        for file_id in sorted(drive_file_ids-deleted_drive_ids):
            adapter.delete_file(file_id,payload['drive_folder_id'])
            deleted_drive_ids.add(file_id)
            payload['drive_deleted_ids']=sorted(deleted_drive_ids)
            job.payload=payload
            db.commit()
            assert_lease(db,job)

    # Keep the Material and its learning history available until Drive confirms
    # every bound remote deletion. If private storage cleanup then fails, the
    # durable job can retry while the learner still sees the material state.
    purge_private_blobs()

    # Stop new writes against the soon-to-be-purged chunks. Any queued job is
    # cancelled; a job already claimed by a worker must finish before the purge.
    active_ingests=db.scalars(select(Job).where(
        Job.learner_id==learner_id,
        Job.kind.in_(INGESTION_JOB_KINDS),
        Job.state.in_(['queued','running']),
    )).all()
    running_ingest=False
    ingest_job_ids=set()
    for candidate in active_ingests:
        if candidate.payload.get('revision_id') not in revision_ids:
            continue
        ingest_job_ids.add(candidate.id)
        if candidate.state=='running':
            running_ingest=True
        else:
            candidate.state='cancelled'
            candidate.error_code='material_deleting'
            candidate.lease_owner=None
            candidate.lease_until=None
    if running_ingest:
        db.commit()
        raise RetryableJobError('material_ingestion_in_flight')

    session_jobs=db.scalars(select(Job).where(
        Job.learner_id==learner_id,
        Job.entity_id.in_(session_ids) if session_ids else False,
        Job.kind.in_(['session.generate','session.assess','session.summary','session.finished']),
        Job.state.in_(['queued','running']),
    )).all() if session_ids else []
    running_session_job=any(candidate.state=='running' for candidate in session_jobs)
    for candidate in session_jobs:
        if candidate.state=='queued':
            candidate.state='cancelled'
            candidate.error_code='material_deleting'
            candidate.lease_owner=None
            candidate.lease_until=None
    if running_session_job:
        db.commit()
        raise RetryableJobError('material_session_in_flight')
    if session_ids:
        db.execute(delete(OutboxEvent).where(
            OutboxEvent.learner_id==learner_id,
            OutboxEvent.aggregate_id.in_(session_ids),
        ))
    db.flush()

    # Purge scope memberships by title, mint a new active scope from the remaining
    # selected titles, and carry forward only unaffected title assessments.
    active=db.scalar(select(ScopeRevision).where(
        ScopeRevision.learner_id==learner_id,
        ScopeRevision.collection_id==collection.id,
        ScopeRevision.active.is_(True),
    ))
    if active and chunk_ids:
        active_items=db.scalars(select(ScopeItem).where(
            ScopeItem.learner_id==learner_id,
            ScopeItem.scope_revision_id==active.id,
        ).order_by(ScopeItem.position)).all()
        if any(item.chunk_id in chunk_ids for item in active_items):
            remaining_ids=[item.chunk_id for item in active_items if item.chunk_id not in chunk_ids]
            previous_assessments=db.scalars(select(TitleAssessment).where(
                TitleAssessment.learner_id==learner_id,
                TitleAssessment.scope_revision_id==active.id,
                TitleAssessment.chunk_id.in_(remaining_ids),
            )).all() if remaining_ids else []
            active.active=False
            db.flush()
            revision_number=(db.scalar(select(func.max(ScopeRevision.revision_number)).where(
                ScopeRevision.learner_id==learner_id,
                ScopeRevision.collection_id==collection.id,
            )) or 0)+1
            next_scope=ScopeRevision(learner_id=learner_id,collection_id=collection.id,revision_number=revision_number,active=True)
            db.add(next_scope);db.flush()
            for position,chunk_id in enumerate(remaining_ids):
                db.add(ScopeItem(learner_id=learner_id,scope_revision_id=next_scope.id,chunk_id=chunk_id,position=position))
            for assessment in previous_assessments:
                db.add(TitleAssessment(
                    learner_id=learner_id,chunk_id=assessment.chunk_id,scope_revision_id=next_scope.id,
                    complete=assessment.complete,rationale=assessment.rationale,
                    evidence_event_ids=list(assessment.evidence_event_ids or []),
                    critical_coverage=dict(assessment.critical_coverage or {}),
                ))

    if session_ids:
        sessions=db.scalars(select(StudySession).where(
            StudySession.learner_id==learner_id,
            StudySession.id.in_(session_ids),
        )).all()
        for session in sessions:
            session.summary_json={}
            session.current_item_id=None
            if session.status not in {'finished','interrupted'}:
                session.status='interrupted'
                session.version+=1
        db.execute(delete(OutboxEvent).where(
            OutboxEvent.learner_id==learner_id,
            OutboxEvent.aggregate_id.in_(session_ids),
        ))

    all_related_jobs=db.scalars(select(Job).where(Job.learner_id==learner_id)).all()
    for candidate in all_related_jobs:
        if candidate.id==job.id:
            continue
        related=(candidate.id in ingest_job_ids or candidate.entity_id in session_ids
                 or candidate.payload.get('revision_id') in revision_ids)
        if related:
            db.delete(candidate)
    if session_ids:
        db.execute(delete(Notification).where(Notification.learner_id==learner_id,Notification.entity_id.in_(session_ids)))
    db.execute(delete(Notification).where(Notification.learner_id==learner_id,Notification.entity_id==material.id))

    db.delete(material)
    db.flush()
    remaining_materials=db.scalars(select(Material).where(
        Material.learner_id==learner_id,
        Material.collection_id==collection.id,
        Material.archived.is_(False),
    ).order_by(Material.position,Material.id)).all()
    for position,row in enumerate(remaining_materials):
        row.position=position
    collection.version+=1
    payload['database_deleted']=True
    payload['deleted_drive_count']=len(drive_file_ids)
    job.payload=payload
    job.entity_id=None
    job.idempotency_key=None
    db.commit()

    purge_private_blobs()
    job.payload={}
    db.commit()
    return {'deleted':True,'drive_files_deleted':len(drive_file_ids)}


def delete_material_handler(db,job):
    try:
        return delete_material(db,job)
    except SourceError as exc:
        if not job.payload.get('database_deleted'):
            material=db.scalar(select(Material).where(Material.id==job.payload.get('material_id'),Material.learner_id==job.learner_id))
            if material:
                material.status='deleting' if exc.retryable else 'needs-attention'
                db.commit()
        if exc.retryable:
            raise RetryableJobError(exc.code) from exc
        raise NeedsAttention(exc.code) from exc

def job_handler(handler):
    def wrapped(db,job):
        try:return handler(db,job)
        except SourceError as exc:
            raise (RetryableJobError(exc.code) if exc.retryable else NeedsAttention(exc.code)) from exc
    return wrapped


def _mark_pdf_attention(db,job,code):
    """Make terminal PDF worker failures visible on both the job and material."""
    db.rollback()
    revision_id=(job.payload or {}).get('revision_id')
    material_id=(job.payload or {}).get('material_id')
    revision=db.scalar(select(MaterialRevision).where(
        MaterialRevision.id==revision_id,MaterialRevision.learner_id==job.learner_id,
    )) if revision_id else None
    material=db.scalar(select(Material).where(
        Material.id==material_id,Material.learner_id==job.learner_id,
    )) if material_id else None
    if material and material.status!='deleting':
        material.status='needs-attention'
    if revision:
        manifest=dict(revision.metadata_json.get('ingestion_manifest') or {})
        manifest['status']='needs-review'
        manifest['warning']=code
        revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest}
    db.commit()


def pdf_job_handler(handler):
    def wrapped(db,job):
        try:
            return handler(db,job)
        except SourceError as exc:
            if exc.retryable:
                raise RetryableJobError(exc.code) from exc
            _mark_pdf_attention(db,job,exc.code)
            raise NeedsAttention(exc.code) from exc
        except NeedsAttention as exc:
            _mark_pdf_attention(db,job,exc.code)
            raise
        except (RetryableJobError,LostLease):
            raise
        except Exception:
            _mark_pdf_attention(db,job,'pdf_pipeline_failed')
            raise
    return wrapped

register('ingest-material',job_handler(ingest_material))
register('ingest-pdf-batch',pdf_job_handler(ingest_pdf_batch))
register('ingest-pdf-finalize',pdf_job_handler(finalize_pdf_material))
register('delete-material',delete_material_handler)
register('drive-provision',job_handler(provision_drive))
register('drive-sync',job_handler(sync_drive))
