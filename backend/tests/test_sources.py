import hashlib
import io
import json
import socket
import pytest
import httpx
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import sessionmaker
from app.db import Base
from app.models import Learner,Collection,Material,MaterialRevision,Chunk,Concept,Citation,ProviderConnection,Job,ScopeRevision,StudySession,SessionItem
from app.ingest import persist_snapshot,parse_descriptor,ingest_material,provision_drive,sync_drive
from app.sources.base import SourceError
from app.sources.local import extract_file
from app.sources.publicweb import validate_url,fetch_public_page
from app.sources.captions import extract_captions
from app.sources.drive import DriveAdapter, encrypt_credentials, decrypt_credentials, SCOPES
from app.storage import LocalStorage
from app.settings import settings


@pytest.fixture
def db(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=__import__('sqlalchemy').pool.StaticPool)
    Base.metadata.create_all(engine)
    session=sessionmaker(engine,expire_on_commit=False)()
    session.add(Learner(id='owner'));session.add(Learner(id='other'));session.commit()
    monkeypatch.setattr(settings,'private_storage_dir',str(tmp_path/'private'))
    yield session
    session.close()


def test_markdown_preserves_headings_lines_and_hashes(db):
    snapshot=extract_file(b'# Cells\nCells contain DNA.\n\n# Energy\nATP stores energy.','notes.md')
    collection=Collection(id='collection',learner_id='owner',name='Biology');db.add(collection);db.flush()
    material=Material(id='material',learner_id='owner',collection_id=collection.id,title='Notes');db.add(material);db.flush()
    revision=MaterialRevision(id='revision',learner_id='owner',collection_id=collection.id,material_id=material.id,content_hash='hash');db.add(revision);db.flush()
    persist_snapshot(db,revision,snapshot);persist_snapshot(db,revision,snapshot)
    assert db.scalar(select(func.count(Chunk.id)))==2
    citation=db.scalar(select(Citation).where(Citation.locator_json['heading'].as_string()=='Cells'))
    assert citation.locator_json['line_start']==1 and citation.locator_json['line_end']==3
    assert citation.excerpt_hash==hashlib.sha256(citation.excerpt.encode()).hexdigest()
    assert db.scalar(select(func.count(Concept.id)))>=2
    assert material.current_revision_id==revision.id


def test_spreadsheets_real_locators():
    snapshot=extract_file('Term,Meaning\nATP,Energy carrier\n'.encode(),'terms.csv')
    assert snapshot.sections[0].locator['row_start']==2
    assert 'Meaning: Energy carrier' in snapshot.sections[0].text
    from openpyxl import Workbook
    book=Workbook();sheet=book.active;sheet.title='Biology';sheet.append(['Term','Meaning']);sheet.append(['DNA','Genetic information']);blob=io.BytesIO();book.save(blob)
    section=extract_file(blob.getvalue(),'terms.xlsx').sections[0]
    assert section.locator['sheet']=='Biology' and section.locator['cell_range']=='A2:B2'


def test_pdf_page_locator_and_scan_needs_attention():
    from pypdf import PdfWriter
    writer=PdfWriter();writer.add_blank_page(width=200,height=200);blob=io.BytesIO();writer.write(blob)
    with pytest.raises(SourceError,match='No text'):extract_file(blob.getvalue(),'scan.pdf')
    with pytest.raises(SourceError):extract_file(b'invalid','broken.pdf')


def test_long_text_chunks_follow_paragraphs_and_keep_exact_lines():
    paragraphs = [' '.join([f'Paragraph {index} explains its own topic.'] * 35) for index in range(8)]
    text = '# Real heading\n' + '\n\n'.join(paragraphs)
    snapshot = extract_file(text.encode(), 'long.md')
    assert len(snapshot.sections) > 1
    for section in snapshot.sections:
        assert len(section.text) <= 4000
        locator = section.locator
        assert text[locator['section_char_start']:locator['section_char_end']] == section.text
        assert locator['heading'] == 'Real heading'
        assert locator['line_start'] == 1 + text[:locator['section_char_start']].count('\n')
        assert locator['line_end'] == 1 + text[:locator['section_char_end']].count('\n')
    assert all(any(paragraph in section.text for section in snapshot.sections) for paragraph in paragraphs)


def test_long_pdf_page_chunks_keep_page_and_original_offsets(monkeypatch):
    from types import SimpleNamespace
    text = '\n\n'.join([' '.join(['A source-supported fact.'] * 45)] * 8)
    monkeypatch.setattr('pypdf.PdfReader', lambda _: SimpleNamespace(is_encrypted=False, pages=[SimpleNamespace(extract_text=lambda: text)]))
    sections = extract_file(b'%PDF-synthetic', 'small.pdf').sections
    assert len(sections) > 1
    assert all(section.locator['page'] == 1 and section.locator['filename'] == 'small.pdf' for section in sections)
    assert all(len(section.text) <= 4000 for section in sections)
    assert all(text[section.locator['section_char_start']:section.locator['section_char_end']] == section.text for section in sections)


@pytest.mark.parametrize('filename,prefix', [('long.txt', '\n\n  '), ('long.md', '\n\n# Original heading\n')])
def test_chunk_lines_resolve_after_leading_blank_lines(filename, prefix):
    text = prefix + '\n\n'.join([' '.join(['Source fact.'] * 140)] * 8) + '\n\n'
    lines = text.splitlines()
    for section in extract_file(text.encode(), filename).sections:
        locator = section.locator
        resolved = '\n'.join(lines[locator['line_start']-1:locator['line_end']]).strip()
        assert resolved == section.text


def test_photo_never_uses_stub_ocr():
    with pytest.raises(SourceError) as unavailable:extract_file(b'\x89PNG\r\n\x1a\nsynthetic','notes.png')
    assert unavailable.value.code=='vision_unavailable'
    calls=[]
    snapshot=extract_file(b'\x89PNG\r\n\x1a\nsynthetic','notes.png',vision=lambda data,mime:(calls.append(mime) or 'Visible source text.'))
    assert calls==['image/png'] and snapshot.sections[0].locator['reading_method']=='vision'


@pytest.mark.parametrize('url',['http://127.0.0.1/a','http://169.254.169.254/latest/meta-data','http://[::1]/','file:///etc/passwd','https://u:p@example.com','https://example.com:8000'])
def test_ssrf_rejected(url):
    with pytest.raises(SourceError):validate_url(url)


def test_mixed_dns_and_redirect_private_rejected(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',80)),(2,1,6,'',('10.0.0.1',80))])
    with pytest.raises(SourceError):validate_url('http://example.org')
    monkeypatch.setattr(socket,'getaddrinfo',lambda host,*a,**k:[(2,1,6,'',('127.0.0.1' if host=='private.example' else '93.184.216.34',80))])
    class Redirect:
        status=302
        def getheader(self,key,default=None):return 'http://private.example' if key=='Location' else default
    class Connection:
        def __init__(self,*a):pass
        def request(self,*a,**k):pass
        def getresponse(self):return Redirect()
        def close(self):pass
    monkeypatch.setattr('app.sources.publicweb.PinnedHTTPConnection',Connection)
    with pytest.raises(SourceError) as exc:fetch_public_page('http://example.org')
    assert exc.value.code=='unsafe_url'


def test_captions_only_authorized_timestamps():
    with pytest.raises(SourceError) as exc:extract_captions('https://youtu.be/abcdefghijk')
    assert exc.value.code=='captions_unavailable'
    snapshot=extract_captions('https://youtu.be/abcdefghijk',lambda identifier:[{'start':1.2,'end':3.5,'text':'Permitted caption','language':'fr'}])
    assert snapshot.sections[0].locator['start_seconds']==1.2
    with pytest.raises(SourceError):extract_captions('https://youtu.be/abcdefghijk',lambda _:[])


def test_private_storage_tenant_checks(tmp_path):
    store=LocalStorage(tmp_path);key=store.put('owner',b'private source')
    assert store.get('owner',key)==b'private source'
    with pytest.raises(SourceError):store.get('other',key)
    with pytest.raises(SourceError):store.get('owner','owner/../../etc/passwd')
    assert (tmp_path/key).stat().st_mode&0o777==0o600


def test_tokens_encrypted_and_bad_key_rejected(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings,'credentials_key',Fernet.generate_key().decode())
    encrypted=encrypt_credentials({'access_token':'synthetic-secret'})
    assert 'synthetic-secret' not in encrypted
    assert decrypt_credentials(encrypted)['access_token']=='synthetic-secret'
    monkeypatch.setattr(settings,'credentials_key',Fernet.generate_key().decode())
    with pytest.raises(SourceError):decrypt_credentials(encrypted)


def test_drive_folder_crash_reconcile_and_upload_receipt():
    calls=[]
    files={}
    def handle(request):
        calls.append((request.method,request.url.path))
        if request.method=='GET' and request.url.path=='/drive/v3/files':
            q=request.url.params.get('q','');found=[v for v in files.values() if v['appProperties']['learningos_identity'] in q]
            return httpx.Response(200,json={'files':found})
        if request.method=='POST' and request.url.path=='/drive/v3/files':
            body=json.loads(request.content);body.update(id='folder',capabilities={'canAddChildren':True});files['folder']=body
            return httpx.Response(200,json=body)
        if request.method=='GET':return httpx.Response(200,json=files['folder'])
        if request.method=='POST' and request.url.path.startswith('/upload/'):
            return httpx.Response(200,headers={'Location':'https://www.googleapis.com/upload/drive/v3/files?upload_id=synthetic'})
        if request.method=='PUT':
            if request.headers.get('Content-Length')=='0':return httpx.Response(308,headers={'Range':'bytes=0-2'})
            result={'id':'file','name':'notes.txt','version':'1','parents':['folder'],'appProperties':{'learningos_identity':'upload:revision'}};files['file']=result
            return httpx.Response(200,json=result)
        return httpx.Response(500)
    adapter=DriveAdapter({'access_token':'synthetic','expires_at':9999999999},client=httpx.Client(transport=httpx.MockTransport(handle)))
    first=adapter.ensure_folder('collection:one','Same name')
    second=adapter.ensure_folder('collection:one','Same name')
    assert first['id']==second['id'] and calls.count(('POST','/drive/v3/files'))==1
    receipts=[]
    result=adapter.upload('folder','upload:revision','notes.txt',b'study','text/plain',{},receipts.append)
    assert receipts and result['parents']==['folder']
    replay=adapter.upload('folder','upload:revision','notes.txt',b'study','text/plain',{},receipts.append)
    assert replay['id']==result['id'] and calls.count(('POST','/upload/drive/v3/files'))==1


def test_descriptor_ownership_never_executes_urls():
    payload={'schema':'learningos.source.v1','owner_id':'other','collection_id':'collection','sections':[],'source_url':'http://127.0.0.1'}
    with pytest.raises(SourceError):parse_descriptor(json.dumps(payload).encode(),'owner','collection')

@pytest.fixture
def client(db):
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from app.ingestion_api import router
    from app.core_api import router as core_router
    from app.db import get_db
    from app.auth import get_learner
    app=FastAPI();app.include_router(core_router,prefix='/api/v1');app.include_router(router,prefix='/api/v1')
    app.dependency_overrides[get_db]=lambda:db
    app.dependency_overrides[get_learner]=lambda:db.get(Learner,'owner')
    with TestClient(app) as client:yield client


def test_upload_api_replay_worker_citation_owner_and_failed_photo(db,client):
    db.add(Collection(id='collection',learner_id='owner',name='Owned'))
    db.add(Collection(id='other-collection',learner_id='other',name='Other'));db.commit()
    args={'files':{'file':('study.md',b'# Cells\nCells contain DNA.','text/markdown')},'data':{'idempotency_key':'upload-one'}}
    response=client.post('/api/v1/collections/collection/materials/upload',**args)
    assert response.status_code==202
    first=response.json();replay=client.post('/api/v1/collections/collection/materials/upload',**args)
    assert replay.json()==first
    changed=client.post('/api/v1/collections/collection/materials/upload',files={'file':('study.md',b'changed','text/markdown')},data={'idempotency_key':'upload-one'})
    assert changed.status_code==409
    assert client.post('/api/v1/collections/other-collection/materials/upload',**args).status_code==404
    job=db.get(Job,first['job_id']);result=ingest_material(db,job);db.commit()
    assert result['status']=='ready' and result['storage_state']=='local-only'
    assert client.get('/api/v1/materials/'+first['material_id']).json()['status']=='ready'
    citation=db.scalar(select(Citation).where(Citation.learner_id=='owner'))
    assert client.get('/api/v1/citations/'+citation.id).json()['excerpt']==citation.excerpt
    assert client.get('/api/v1/material-revisions/'+first['revision_id']+'/original').content==b'# Cells\nCells contain DNA.'
    photo=client.post('/api/v1/collections/collection/materials/upload',files={'file':('photo.png',b'\x89PNG\r\n\x1a\nsynthetic','image/png')},data={'idempotency_key':'photo-one'}).json()
    with pytest.raises(SourceError) as exc:ingest_material(db,db.get(Job,photo['job_id']))
    assert exc.value.code=='vision_unavailable'
    assert client.get('/api/v1/materials/'+photo['material_id']).json()['status']=='needs-attention'


def test_connection_and_speech_unavailable_truthful(db,client,monkeypatch):
    monkeypatch.setattr(settings,'drive_client_id',None)
    assert client.get('/api/v1/connections/drive/connect').status_code==503
    assert client.get('/api/v1/speech/capabilities').json()['languages'][3]['verified'] is False
    db.add(Collection(id='speech-collection',learner_id='owner',name='Voice'));db.flush()
    intake=client.post('/api/v1/collections/speech-collection/materials',files={'file':('speech.txt',b'A source-grounded idea.','text/plain')},data={'idempotency_key':'speech-material'}).json()
    ingest_material(db,db.get(Job,intake['job_id']));db.flush()
    chunk=db.scalar(select(Chunk));concept=db.scalar(select(Concept))
    scope=ScopeRevision(id='speech-scope',learner_id='owner',collection_id='speech-collection',revision_number=1);db.add(scope);db.flush()
    session=StudySession(id='speech-session',learner_id='owner',collection_id='speech-collection',scope_revision_id=scope.id,status='awaiting_answer');db.add(session);db.flush()
    item=SessionItem(id='speech-item',learner_id='owner',session_id=session.id,concept_id=concept.id,chunk_id=chunk.id,teaching='Source-grounded teaching.',public_question='What does the source establish?',generation_locale='en');db.add(item);session.current_item_id=item.id;db.commit()
    assert client.post('/api/v1/sessions/speech-session/speech/synthesize',json={'item_id':item.id,'message_id':'question'}).status_code==503
    import wave
    audio=io.BytesIO()
    with wave.open(audio,'wb') as recording:
        recording.setnchannels(1);recording.setsampwidth(2);recording.setframerate(8000);recording.writeframes(b'\x00\x00'*8000)
    assert client.post('/api/v1/sessions/speech-session/speech/transcribe',data={'item_id':item.id},files={'audio':('voice.wav',audio.getvalue(),'audio/wav')}).status_code==503


@pytest.fixture
def configured_drive(monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings, 'app_mode', 'live')
    monkeypatch.setattr(settings, 'drive_client_id', 'synthetic-web-client')
    monkeypatch.setattr(settings, 'drive_client_secret', 'synthetic-client-secret')
    monkeypatch.setattr(settings, 'credentials_key', Fernet.generate_key().decode())
    monkeypatch.setattr(settings, 'public_url', 'http://127.0.0.1:3000')
    monkeypatch.setattr(settings, 'drive_redirect_uri', 'http://127.0.0.1:3000/api/v1/connections/drive/callback')


@pytest.mark.parametrize('mode', ['demo', 'test'])
def test_demo_drive_is_unavailable_even_with_credentials(db, client, configured_drive, monkeypatch, mode):
    monkeypatch.setattr(settings, 'app_mode', mode)
    row = client.get('/api/v1/connections').json()[0]
    assert row['provider'] == 'drive' and row['setup_state'] == 'demo'
    assert row['configured'] is False
    assert 'synthetic-client-secret' not in json.dumps(row)
    response = client.post('/api/v1/connections/drive/connect')
    assert response.status_code == 503
    assert response.json()['detail']['code'] == 'drive_demo_unavailable'
    assert db.scalar(select(func.count(ProviderConnection.id))) == 0


@pytest.mark.parametrize('field,value', [
    ('drive_client_id', None), ('drive_client_secret', None),
    ('credentials_key', 'invalid-encryption-key'),
    ('drive_redirect_uri', 'http://localhost:3000/api/v1/connections/drive/callback'),
    ('public_url', 'http://untrusted.example:3000'),
    ('public_url', 'http://127.0.0.1:99999'),
])
def test_drive_setup_errors_do_not_offer_connect_or_mutate(db, client, configured_drive, monkeypatch, field, value):
    monkeypatch.setattr(settings, field, value)
    row = client.get('/api/v1/connections').json()[0]
    assert row['configured'] is False and row['setup_state'] == 'unconfigured'
    assert row['status'] == 'disconnected'
    assert client.post('/api/v1/connections/drive/connect').status_code == 503
    assert db.scalar(select(func.count(ProviderConnection.id))) == 0


def test_configured_drive_oauth_preserves_pkce_and_exact_callback(db, client, configured_drive, monkeypatch):
    from urllib.parse import urlsplit, parse_qs
    import base64
    row = client.get('/api/v1/connections').json()[0]
    assert row['configured'] is True and row['setup_state'] == 'ready'
    assert row['status'] == 'disconnected', 'Configuration is not proof of consent'
    response = client.post('/api/v1/connections/drive/connect')
    assert response.status_code == 200
    url = urlsplit(response.json()['authorization_url'])
    assert url.scheme == 'https' and url.hostname == 'accounts.google.com'
    query = parse_qs(url.query)
    assert set(query['scope'][0].split()) == set(SCOPES)
    assert query['redirect_uri'] == [settings.drive_redirect_uri]
    connection = db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id == 'owner'))
    checkpoint = dict(connection.checkpoint)
    verifier = decrypt_credentials(checkpoint['oauth_verifier'])['verifier']
    expected = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip('=')
    assert query['code_challenge'] == [expected]
    assert query['code_challenge_method'] == ['S256']
    assert checkpoint['oauth_state_hash'] == hashlib.sha256(query['state'][0].encode()).hexdigest()

    def token_exchange(url, *, data, timeout):
        assert url == 'https://oauth2.googleapis.com/token'
        assert data['redirect_uri'] == settings.drive_redirect_uri
        assert data['code_verifier'] == verifier
        return httpx.Response(200, json={'access_token':'synthetic-access', 'refresh_token':'synthetic-refresh',
                                        'expires_in':3600, 'scope':' '.join(SCOPES)})
    monkeypatch.setattr('app.ingestion_api.httpx.post', token_exchange)
    callback = client.get('/api/v1/connections/drive/callback', params={'state':query['state'][0], 'code':'synthetic-code'}, follow_redirects=False)
    assert callback.status_code == 307
    db.refresh(connection)
    assert connection.status == 'connected' and connection.encrypted_credentials
    assert not any(k.startswith('oauth_') for k in connection.checkpoint)
    public = client.get('/api/v1/connections').json()
    assert public[0]['status'] == 'connected'
    assert 'synthetic-refresh' not in json.dumps(public)
    assert settings.credentials_key not in json.dumps(public)


class StubDrive:
    def __init__(self):self.folders={};self.files={};self.uploads=0;self.next=0
    def ensure_folder(self,identity,name,parent=None,existing_id=None):
        if identity not in self.folders:
            self.next+=1;self.folders[identity]={'id':f'folder{self.next}','name':name,'parents':[parent] if parent else [],'mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True}}
        return self.folders[identity]
    def get_file(self,identifier):return next(v for v in self.folders.values() if v['id']==identifier)
    def upload(self,folder,identity,name,data,mime,receipt,persist):
        for file in self.files.values():
            if file['appProperties']['learningos_identity']==identity:return file
        self.uploads+=1;result={'id':f'ui{self.uploads}','name':name,'mimeType':mime,'version':'1','parents':[folder],'appProperties':{'learningos_identity':identity,'learningos_schema':'1'},'data':data,'size':len(data)};self.files[result['id']]=result;return result
    def list_files(self,folder):return [f for f in self.files.values() if folder in f['parents']]
    def download(self,identifier,max_bytes):return self.files[identifier]['data']


def test_drive_ui_scan_dedup_manual_drop_version_and_removal(db,client,monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings,'credentials_key',Fernet.generate_key().decode())
    connection=ProviderConnection(learner_id='owner',provider='drive',status='connected',scopes=SCOPES,encrypted_credentials=encrypt_credentials({'synthetic':True}));db.add(connection)
    collection=Collection(id='collection',learner_id='owner',name='Same',storage_mode='drive',provisioning_state='pending');db.add(collection);db.commit()
    adapter=StubDrive();monkeypatch.setattr('app.ingest.drive_adapter',lambda *_:adapter)
    provision_job=Job(learner_id='owner',kind='drive-provision',payload={});db.add(provision_job);db.flush()
    provision_drive(db,provision_job);provision_drive(db,provision_job)
    assert len(adapter.folders)==2
    intake=client.post('/api/v1/collections/collection/materials/upload',files={'file':('study.md',b'# Cells\nDNA encodes information.','text/markdown')},data={'idempotency_key':'drive-one'}).json()
    ingest_material(db,db.get(Job,intake['job_id']));db.commit()
    assert db.get(MaterialRevision,intake['revision_id']).storage_state=='saved-to-drive'
    poll=Job(learner_id='owner',kind='drive-sync',payload={'collection_id':'collection'});db.add(poll);db.flush()
    assert sync_drive(db,poll)['discovered']==0
    adapter.files['manual']={'id':'manual','name':'direct.txt','mimeType':'text/plain','version':'1','parents':[collection.drive_folder_id],'data':b'Direct study content.','size':21,'appProperties':{}}
    assert sync_drive(db,poll)['discovered']==1
    assert sync_drive(db,poll)['discovered']==0
    revision=db.scalar(select(MaterialRevision).where(MaterialRevision.drive_file_id=='manual'))
    ingestjob=db.scalar(select(Job).where(Job.idempotency_key==f'ingest:{revision.id}'))
    ingest_material(db,ingestjob);db.commit()
    old_revision=revision.id;old_material=revision.material_id
    adapter.files['manual'].update(version='2',data=b'Updated source content.')
    assert sync_drive(db,poll)['discovered']==1
    newer=db.scalar(select(MaterialRevision).where(MaterialRevision.drive_file_id=='manual',MaterialRevision.provider_revision=='2'))
    assert newer.id!=old_revision and newer.material_id==old_material
    adapter.files.pop('manual');sync_drive(db,poll)
    assert db.get(MaterialRevision,old_revision).metadata_json['requires_reconciliation'] is True
    assert db.get(Material,old_material).current_revision_id==old_revision


def test_drive_link_receipt_replay_preserve_snapshot(db,client,monkeypatch):
    from app.sources.base import SourceSnapshot,ExtractedSection
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings,'credentials_key',Fernet.generate_key().decode())
    db.add(ProviderConnection(learner_id='owner',provider='drive',status='connected',scopes=SCOPES,encrypted_credentials=encrypt_credentials({'synthetic':True})))
    collection=Collection(id='collection',learner_id='owner',name='Web',storage_mode='drive',provisioning_state='pending');db.add(collection);db.commit()
    adapter=StubDrive();monkeypatch.setattr('app.ingest.drive_adapter',lambda *_:adapter)
    job=Job(learner_id='owner',kind='drive-provision',payload={});db.add(job);db.flush();provision_drive(db,job)
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    calls=[]
    def fetch(_):calls.append(1);return SourceSnapshot([ExtractedSection('Energy','ATP is an energy carrier.','web',{'url':'https://example.org/','paragraph':1,'snapshot_at':'2026-01-01'})],'https://example.org/')
    monkeypatch.setattr('app.ingest.fetch_public_page',fetch)
    result=client.post('/api/v1/collections/collection/materials/link',json={'url':'https://example.org/','idempotency_key':'web-one'})
    assert result.status_code==202
    job=db.get(Job,result.json()['job_id']);ingest_material(db,job);db.commit()
    descriptor=json.loads(next(iter(adapter.files.values()))['data'])
    import jsonschema
    from pathlib import Path
    jsonschema.validate(descriptor,json.loads((Path(__file__).resolve().parents[2]/'contracts/link-source.schema.json').read_text()))
    assert descriptor['schema_version']==1 and descriptor['segments'][0]['paragraph']==1
    mirror=Job(learner_id='owner',kind='ingest-material',payload={'revision_id':result.json()['revision_id'],'mirror':True});db.add(mirror);db.flush();ingest_material(db,mirror)
    assert len(calls)==1 and adapter.uploads==1
    assert db.scalar(select(func.count(Chunk.id)))==1


def test_concept_grouping_keeps_original_whitespace_exact(db):
    text='# Exact source\n'+''.join(f'Sentence {n} is preserved.  ' for n in range(1,21))
    snapshot=extract_file(text.encode(),'exact.md')
    collection=Collection(id='collection',learner_id='owner',name='Exact');db.add(collection);db.flush()
    material=Material(id='material',learner_id='owner',collection_id=collection.id,title='Exact');db.add(material);db.flush()
    revision=MaterialRevision(id='revision',learner_id='owner',collection_id=collection.id,material_id=material.id,content_hash='hash',metadata_json={'filename':'exact.md'});db.add(revision);db.flush()
    persist_snapshot(db,revision,snapshot)
    chunk=db.scalar(select(Chunk))
    citations=db.scalars(select(Citation)).all()
    assert len(citations)<=9
    assert all(c.excerpt in chunk.text for c in citations)
    assert all(chunk.text[c.locator_json['excerpt_start']:c.locator_json['excerpt_end']]==c.excerpt for c in citations if 'concept_segment' in c.locator_json)
    assert all('# Exact source' not in c.excerpt for c in citations if 'concept_segment' in c.locator_json)


def test_encrypted_pdf_truthful():
    from pypdf import PdfWriter
    writer=PdfWriter();writer.add_blank_page(width=200,height=200);writer.encrypt('synthetic');blob=io.BytesIO();writer.write(blob)
    with pytest.raises(SourceError) as exc:extract_file(blob.getvalue(),'locked.pdf')
    assert exc.value.code=='encrypted_pdf'


def test_drive_interruption_resumes_same_upload_and_permission_fails():
    calls=[];uploaded=[]
    def handle(request):
        if request.method=='GET' and request.url.path=='/drive/v3/files':return httpx.Response(200,json={'files':[]})
        if request.method=='GET':return httpx.Response(200,json={'id':'folder','capabilities':{'canAddChildren':True}})
        if request.method=='POST':
            calls.append('initiate');return httpx.Response(200,headers={'Location':'https://www.googleapis.com/upload/drive/v3/files?upload_id=synthetic'})
        if request.method=='PUT' and request.headers['Content-Length']=='0':return httpx.Response(308,headers={'Range':'bytes=0-2'})
        uploaded.append(request.content)
        if len(uploaded)==1:raise httpx.ReadTimeout('synthetic interruption')
        return httpx.Response(200,json={'id':'file','parents':['folder'],'version':'1'})
    adapter=DriveAdapter({'access_token':'synthetic','expires_at':9999999999},client=httpx.Client(transport=httpx.MockTransport(handle)))
    receipts=[]
    with pytest.raises(SourceError) as exc:adapter.upload('folder','upload:test','file.txt',b'abcdef','text/plain',{},receipts.append)
    assert exc.value.retryable is True and len(receipts)==1
    confirmed=adapter.upload('folder','upload:test','file.txt',b'abcdef','text/plain',receipts[0],receipts.append)
    assert confirmed['id']=='file' and calls==['initiate'] and uploaded[-1]==b'def'
    denied=DriveAdapter({'access_token':'synthetic','expires_at':9999999999},client=httpx.Client(transport=httpx.MockTransport(lambda _:httpx.Response(403))))
    with pytest.raises(SourceError) as permission:denied.list_files('folder')
    assert permission.value.code=='drive_permission' and not permission.value.retryable


def test_failed_connected_upload_is_not_local_success(db,client,monkeypatch):
    db.add(Collection(id='collection',learner_id='owner',name='Drive',storage_mode='drive',provisioning_state='pending'));db.commit()
    response=client.post('/api/v1/collections/collection/materials/upload',files={'file':('study.txt',b'Private source.','text/plain')},data={'idempotency_key':'pending-drive'}).json()
    job=db.get(Job,response['job_id'])
    with pytest.raises(SourceError) as pending:ingest_material(db,job)
    assert pending.value.code=='folder_pending' and pending.value.retryable
    revision=db.get(MaterialRevision,response['revision_id'])
    assert revision.storage_state=='upload-pending'
    assert db.get(Material,response['material_id']).current_revision_id is None
    assert db.scalar(select(func.count(Chunk.id)))==0


def test_local_storage_concurrent_identical_writes_are_atomic(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    import threading
    from pathlib import Path
    storage=LocalStorage(tmp_path/'private');barrier=threading.Barrier(2)
    real_replace=__import__('os').replace
    def synchronized_replace(source,destination):
        barrier.wait(timeout=5)
        return real_replace(source,destination)
    monkeypatch.setattr('app.storage.os.replace',synchronized_replace)
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(storage.put,'owner',b'identical') for _ in range(2)]
        keys=[f.result() for f in futures]
    assert keys[0]==keys[1]
    assert storage.get('owner',keys[0])==b'identical'
    assert not list((tmp_path/'private'/'owner').glob('*.tmp'))


def test_s3_consumes_declared_configuration_and_aws_fallback(monkeypatch):
    from app.storage import S3Storage
    calls=[]
    monkeypatch.setattr('boto3.client',lambda service,**kwargs:(calls.append((service,kwargs)) or object()))
    monkeypatch.setenv('STORAGE_REGION','test-region')
    monkeypatch.setenv('STORAGE_ACCESS_KEY','synthetic-access')
    monkeypatch.setenv('STORAGE_SECRET_KEY','synthetic-secret')
    S3Storage()
    options=calls[-1][1]
    assert options['region_name']=='test-region'
    assert options['aws_access_key_id']=='synthetic-access' and options['aws_secret_access_key']=='synthetic-secret'
    for name in ['STORAGE_REGION','STORAGE_ACCESS_KEY','STORAGE_SECRET_KEY']:monkeypatch.delenv(name)
    S3Storage()
    assert 'aws_access_key_id' not in calls[-1][1] and 'region_name' not in calls[-1][1]


def test_dns_unavailable_retryable_without_private_destination_bypass(monkeypatch):
    def unavailable(*args,**kwargs):raise socket.gaierror('synthetic unavailable')
    monkeypatch.setattr(socket,'getaddrinfo',unavailable)
    with pytest.raises(SourceError) as exc:validate_url('https://raw.githubusercontent.com/public/study')
    assert exc.value.code=='web_dns_unavailable' and exc.value.retryable


def test_pasted_link_descriptor_cannot_bypass_small_quota(db,client,monkeypatch):
    from app.sources.base import SourceSnapshot,ExtractedSection
    db.add(Collection(id='collection',learner_id='owner',name='Web'));db.commit()
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(2,1,6,'',('93.184.216.34',443))])
    monkeypatch.setattr('app.ingest.fetch_public_page',lambda _:SourceSnapshot([ExtractedSection('Source','Study content.','web',{'paragraph':1})],'https://example.org/'))
    monkeypatch.setenv('SOURCE_QUOTA_BYTES','1')
    response=client.post('/api/v1/collections/collection/materials/link',json={'url':'https://example.org/','idempotency_key':'quota-link'}).json()
    with pytest.raises(SourceError) as exc:ingest_material(db,db.get(Job,response['job_id']))
    assert exc.value.code=='source_quota_exceeded'
    revision=db.get(MaterialRevision,response['revision_id'])
    assert revision.private_blob_key is None and revision.size==0
    assert db.scalar(select(func.count(Chunk.id)))==0


def test_direct_drop_bytes_and_material_count_quota(db,monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings,'credentials_key',Fernet.generate_key().decode())
    db.add(ProviderConnection(learner_id='owner',provider='drive',status='connected',scopes=SCOPES,encrypted_credentials=encrypt_credentials({'synthetic':True})))
    collection=Collection(id='collection',learner_id='owner',name='Drive',storage_mode='drive');db.add(collection);db.commit()
    adapter=StubDrive();monkeypatch.setattr('app.ingest.drive_adapter',lambda *_:adapter)
    provision=Job(learner_id='owner',kind='drive-provision',payload={});db.add(provision);db.flush();provision_drive(db,provision)
    adapter.files['manual']={'id':'manual','name':'direct.txt','mimeType':'text/plain','version':'1','parents':[collection.drive_folder_id],'data':b'four','size':4,'appProperties':{}}
    poll=Job(learner_id='owner',kind='drive-sync',payload={'collection_id':collection.id});db.add(poll);db.commit()
    monkeypatch.setenv('SOURCE_QUOTA_BYTES','1')
    with pytest.raises(SourceError) as exc:sync_drive(db,poll)
    assert exc.value.code=='source_quota_exceeded'
    assert db.scalar(select(func.count(MaterialRevision.id)))==0
    monkeypatch.setenv('SOURCE_QUOTA_BYTES','1000');monkeypatch.setenv('SOURCE_MAX_MATERIALS','0')
    with pytest.raises(SourceError) as count:sync_drive(db,poll)
    assert count.value.code=='source_quota_exceeded' and db.scalar(select(func.count(Material.id)))==0


def test_quota_serializes_concurrent_reservations_file_sqlite(tmp_path,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from app.ingest import reserve_source_quota
    monkeypatch.setenv('SOURCE_QUOTA_BYTES','6')
    engine=create_engine(f'sqlite:///{tmp_path/"quota.db"}',connect_args={'check_same_thread':False,'timeout':10})
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as session:
        session.add(Learner(id='owner'));session.flush();session.add(Collection(id='collection',learner_id='owner',name='Quota'));session.commit()
    def reserve(number):
        with factory() as session:
            try:
                reserve_source_quota(session,'owner','collection',4,new_material=True)
                material=Material(learner_id='owner',collection_id='collection',title=str(number));session.add(material);session.flush()
                session.add(MaterialRevision(learner_id='owner',collection_id='collection',material_id=material.id,content_hash=str(number),size=4));session.commit();return 'reserved'
            except SourceError as exc:return exc.code
    with ThreadPoolExecutor(max_workers=2) as executor:results=list(executor.map(reserve,[1,2]))
    assert sorted(results)==['reserved','source_quota_exceeded']
    with factory() as session:assert session.scalar(select(func.sum(MaterialRevision.size)))==4


def test_link_intake_queues_safe_hostname_when_dns_unavailable(db,client,monkeypatch):
    db.add(Collection(id='collection',learner_id='owner',name='Pending web'));db.commit()
    def unavailable(*args,**kwargs):raise socket.gaierror('synthetic DNS unavailable')
    monkeypatch.setattr(socket,'getaddrinfo',unavailable)
    response=client.post('/api/v1/collections/collection/link',json={'url':'https://example.com/study','idempotency_key':'pending-link'})
    assert response.status_code==202 and response.json()['status']=='queued'
    revision=db.get(MaterialRevision,response.json()['revision_id'])
    assert revision.private_blob_key is None and revision.extracted_text==''
    with pytest.raises(SourceError) as exc:ingest_material(db,db.get(Job,response.json()['job_id']))
    assert exc.value.code=='web_dns_unavailable' and exc.value.retryable
    assert revision.private_blob_key is None and db.get(Material,revision.material_id).status=='queued'
    for unsafe in ['http://127.0.0.1/','https://10.0.0.1/','http://localhost/','https://metadata.google.internal/','https://user:password@example.com/','http://2130706433/']:
        assert client.post('/api/v1/collections/collection/link',json={'url':unsafe,'idempotency_key':'unsafe-link'}).status_code==422


def test_source_openapi_typed_public_models_and_no_duplicate_paths(client):
    document=client.get('/openapi.json').json()
    response=document['paths']['/api/v1/collections/{collection_id}/materials']['post']['responses']['202']['content']['application/json']['schema']
    assert response['$ref'].endswith('/IntakeDTO')
    assert '/api/v1/collections/{collection_id}/storage-status' in document['paths']
    assert '/api/v1/materials/{material_id}/storage-status' in document['paths']
    assert document['paths']['/api/v1/citations/{citation_id}']['get']['responses']['200']['content']['application/json']['schema']['$ref'].endswith('/CitationDTO')
    schemas=document['components']['schemas']
    assert 'encrypted_credentials' not in str(schemas['ConnectionDTO'])
    assert 'resumable_url' not in str(schemas['MaterialStorageDTO'])


def test_source_language_file_intake_persists_before_extraction(db, client):
    db.add(Collection(id='language-collection', learner_id='owner', name='Languages')); db.commit()
    args = {'files': {'file': ('genes.md', b'# Genes\nDNA carries genetic information.', 'text/markdown')}, 'data': {'idempotency_key': 'language-file', 'source_language': 'FR-ca'}}
    response = client.post('/api/v1/collections/language-collection/materials', **args)
    assert response.status_code == 202
    receipt = response.json(); revision = db.get(MaterialRevision, receipt['revision_id'])
    assert receipt['source_language'] == revision.source_language == 'fr-CA'
    ingest_material(db, db.get(Job, receipt['job_id'])); db.commit()
    assert revision.source_language == 'fr-CA'  # Local parser returns und.
    assert client.get('/api/v1/collections/language-collection/materials').json()['items'][0]['source_language'] == 'fr-CA'
    assert client.post('/api/v1/collections/language-collection/materials', **args).json()['material_id'] == receipt['material_id']
    changed = {**args, 'data': {**args['data'], 'source_language': 'de'}}
    assert client.post('/api/v1/collections/language-collection/materials', **changed).status_code == 409


def test_source_language_link_intake_supports_beyond_ui_languages(db, client):
    db.add(Collection(id='language-links', learner_id='owner', name='Languages')); db.commit()
    body = {'url': 'https://example.org/study', 'idempotency_key': 'language-link', 'source_language': 'sw-KE'}
    response = client.post('/api/v1/collections/language-links/link', json=body)
    assert response.status_code == 202
    assert db.get(MaterialRevision, response.json()['revision_id']).source_language == 'sw-KE'
    assert client.post('/api/v1/collections/language-links/link', json={**body, 'source_language': 'en'}).status_code == 409


@pytest.mark.parametrize('code', ['en_US', 'en--GB', 'en-1234-!', 'a', 'en-x', 'en-' + 'a' * 31, 'en<script>'])
def test_source_language_invalid_code_rejected_without_intake(db, client, code):
    db.add(Collection(id='invalid-language', learner_id='owner', name='Languages')); db.commit()
    assert client.post('/api/v1/collections/invalid-language/materials', files={'file': ('source.txt', b'A source.', 'text/plain')}, data={'idempotency_key': 'invalid-language', 'source_language': code}).status_code == 422
    assert client.post('/api/v1/collections/invalid-language/link', json={'url': 'https://example.org/study', 'idempotency_key': 'invalid-link', 'source_language': code}).status_code == 422
    assert db.scalar(select(func.count(Material.id))) == 0


def test_source_language_correction_preserves_sources_citations_and_turn(db, client):
    db.add(Collection(id='correct-language', learner_id='owner', name='Languages')); db.commit()
    data = b'# Cells\nCells contain DNA.'
    receipt = client.post('/api/v1/collections/correct-language/materials', files={'file': ('cells.md', data, 'text/markdown')}, data={'idempotency_key': 'correct-language', 'source_language': 'en'}).json()
    revision = db.get(MaterialRevision, receipt['revision_id']); ingest_material(db, db.get(Job, receipt['job_id'])); db.commit()
    chunk = db.scalar(select(Chunk).where(Chunk.material_revision_id == revision.id))
    concept = db.scalar(select(Concept).where(Concept.chunk_id == chunk.id))
    scope = ScopeRevision(learner_id='owner', collection_id='correct-language', revision_number=1); db.add(scope); db.flush()
    session = StudySession(learner_id='owner', collection_id='correct-language', scope_revision_id=scope.id); db.add(session); db.flush()
    snapshot = {'source_language': 'en', 'source_revision_id': revision.id, 'citation_ids': concept.citation_ids, 'expected_answer': 'private fixture'}
    turn = SessionItem(learner_id='owner', session_id=session.id, concept_id=concept.id, chunk_id=chunk.id, question_json_private=snapshot); db.add(turn); db.commit()
    identity = (revision.id, revision.content_hash, revision.private_blob_key, revision.extracted_text)
    citations = [(r.id, r.excerpt, r.excerpt_hash, r.locator_json.copy()) for r in db.scalars(select(Citation).where(Citation.revision_id == revision.id)).all()]
    url = '/api/v1/materials/' + receipt['material_id'] + '/source-language'
    corrected = client.patch(url, json={'source_language': 'zh-Hans'})
    assert corrected.status_code == 200 and corrected.json()['source_language'] == 'zh-Hans'
    assert identity == (revision.id, revision.content_hash, revision.private_blob_key, revision.extracted_text)
    assert citations == [(r.id, r.excerpt, r.excerpt_hash, r.locator_json) for r in db.scalars(select(Citation).where(Citation.revision_id == revision.id)).all()]
    assert turn.question_json_private == snapshot
    assert client.get('/api/v1/material-revisions/' + revision.id + '/original').content == data
    assert client.patch(url, json={'source_language': 'und'}).status_code == 200
    assert revision.source_language == 'und' and turn.question_json_private['source_language'] == 'en'
    db.add(Collection(id='foreign-language', learner_id='other', name='Other')); db.flush()
    foreign = Material(learner_id='other', collection_id='foreign-language', title='Private'); db.add(foreign); db.commit()
    assert client.patch('/api/v1/materials/' + foreign.id + '/source-language', json={'source_language': 'fr'}).status_code == 404
    assert client.patch(url, json={'source_language': 'en_US'}).status_code == 422
    assert client.patch(url, json={}).status_code == 422
    material = db.get(Material, receipt['material_id']); material.archived = True; db.commit()
    assert client.patch(url, json={'source_language': 'fr'}).status_code == 409


def test_source_language_unknown_uses_actual_adapter_metadata_and_explicit_unknown_stays(db):
    from app.sources.base import SourceSnapshot, ExtractedSection
    collection = Collection(learner_id='owner', name='Captions'); db.add(collection); db.flush()
    material = Material(learner_id='owner', collection_id=collection.id, title='Captions'); db.add(material); db.flush()
    snapshot = SourceSnapshot([ExtractedSection('Caption', 'Un extrait original.', 'paragraph', {'paragraph': 1})], source_language='fr')
    revision = MaterialRevision(learner_id='owner', collection_id=collection.id, material_id=material.id, content_hash='caption-language', source_language='und', metadata_json={'source_language_provenance': 'unknown'}); db.add(revision); db.flush()
    persist_snapshot(db, revision, snapshot)
    assert revision.source_language == 'fr'
    other_material = Material(learner_id='owner', collection_id=collection.id, title='Corrected'); db.add(other_material); db.flush()
    explicit = MaterialRevision(learner_id='owner', collection_id=collection.id, material_id=other_material.id, content_hash='explicit-unknown', source_language='und', metadata_json={'source_language_provenance': 'learner'}); db.add(explicit); db.flush()
    persist_snapshot(db, explicit, snapshot)
    assert explicit.source_language == 'und'


def test_source_language_worker_refreshes_concurrent_correction_from_second_session(db):
    from sqlalchemy.orm import Session
    collection = Collection(learner_id='owner', name='Concurrent labels'); db.add(collection); db.flush()
    material = Material(learner_id='owner', collection_id=collection.id, title='Original'); db.add(material); db.flush()
    revision = MaterialRevision(learner_id='owner', collection_id=collection.id, material_id=material.id, content_hash='unchanged-original-hash', source_language='en', metadata_json={'filename': 'source.txt', 'source_language_provenance': 'learner'}); db.add(revision); db.commit()
    identity = (revision.id, revision.content_hash)
    # The worker keeps its loaded ORM instance while extraction/provider IO is
    # outside the transaction. A separate request corrects that revision label.
    with Session(bind=db.get_bind(), expire_on_commit=False) as request_db:
        corrected = request_db.get(MaterialRevision, revision.id)
        corrected.source_language = 'ar'
        corrected.metadata_json = {**corrected.metadata_json, 'source_language_provenance': 'learner'}
        request_db.commit()
    assert revision.source_language == 'en'  # Actually stale worker cache.
    persist_snapshot(db, revision, extract_file(b'Original text remains unchanged.', 'source.txt')); db.commit()
    assert revision.source_language == 'ar'
    assert (revision.id, revision.content_hash) == identity
    assert revision.extracted_text == 'Original text remains unchanged.'


@pytest.mark.parametrize('scenario,expected',[
    ('denied','oauth_denied'),('network','oauth_network'),('bad_status','oauth_token_exchange_failed'),
    ('bad_json','oauth_network'),('scope','drive_scope_incomplete'),('refresh','drive_refresh_token_missing')])
def test_drive_consent_failure_returns_to_ui_consumes_state_and_never_leaks_tokens(db,client,configured_drive,monkeypatch,scenario,expected):
    from urllib.parse import urlsplit,parse_qs
    start=client.post('/api/v1/connections/drive/connect')
    state=parse_qs(urlsplit(start.json()['authorization_url']).query)['state'][0]
    def exchange(*args,**kwargs):
        if scenario=='network':raise httpx.ConnectError('private-network-detail')
        if scenario=='bad_status':return httpx.Response(503)
        if scenario=='bad_json':return httpx.Response(200,text='not-json')
        return httpx.Response(200,json={'access_token':'private-access-fixture','refresh_token':'' if scenario=='refresh' else 'private-refresh-fixture',
            'scope':' '.join(SCOPES) if scenario!='scope' else SCOPES[0],'expires_in':3600})
    monkeypatch.setattr('app.ingestion_api.httpx.post',exchange)
    params={'state':state,'error':'access_denied'} if scenario=='denied' else {'state':state,'code':'private-code-fixture'}
    response=client.get('/api/v1/connections/drive/callback',params=params,follow_redirects=False)
    assert response.status_code==307
    assert response.headers['location']==settings.frontend_url.rstrip('/')+'/connections?drive_error='+expected
    assert 'private-' not in response.headers['location']
    connection=db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id=='owner',ProviderConnection.provider=='drive'))
    assert connection.error_code==expected and not connection.encrypted_credentials
    assert not any(key.startswith('oauth_') for key in connection.checkpoint)
    assert client.get('/api/v1/connections/drive/callback',params=params,follow_redirects=False).status_code==400
