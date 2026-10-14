import hashlib
import io
import json
import socket
import pytest
import httpx
from sqlalchemy import create_engine, select, func, event
from sqlalchemy.orm import sessionmaker
from app.db import Base,utcnow
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
    @event.listens_for(engine,'connect')
    def sqlite_foreign_keys(connection,_):connection.execute('PRAGMA foreign_keys=ON')
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
    assert citation.locator_json['line_start']==2 and citation.locator_json['line_end']==2
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


def test_customer_support_token_windows_keep_exact_offsets_and_twenty_token_overlap():
    import tiktoken
    from app.sources.local import split_teaching_windows

    text=' '.join(f'Sentence {number} preserves an exact source fact.' for number in range(180))
    windows=split_teaching_windows(text)
    encoder=tiktoken.get_encoding('cl100k_base')
    assert len(windows)>1
    for window in windows:
        assert text[window['start']:window['end']]==window['text']
        assert text[window['core_start']:window['core_end']]==window['core_text']
        assert len(encoder.encode(window['text']))<=160
    for previous,current in zip(windows,windows[1:]):
        assert current['token_start']==previous['token_end']-20
        assert current['core_token_start']==previous['token_end']
        assert current['core_start']>=previous['core_end']


def test_docx_sections_keep_headings_and_table_rows_in_body_order():
    from docx import Document as DocxDocument

    document=DocxDocument()
    document.add_heading('Eligibility',level=1)
    document.add_paragraph('Refunds are available within thirty days.')
    table=document.add_table(rows=1,cols=2)
    table.rows[0].cells[0].text='Plan'
    table.rows[0].cells[1].text='Annual fee'
    document.add_heading('Exclusions',level=1)
    document.add_paragraph('Digital goods are final.')
    blob=io.BytesIO();document.save(blob)
    sections=extract_file(blob.getvalue(),'policy.docx').sections
    eligibility=next(section for section in sections if section.title=='Eligibility')
    exclusions=next(section for section in sections if section.title=='Exclusions')
    assert 'Refunds are available' in eligibility.text
    assert 'Plan | Annual fee' in eligibility.text
    assert 'Digital goods' not in eligibility.text
    assert 'Digital goods are final' in exclusions.text
    assert eligibility.locator['docx_block_start']<exclusions.locator['docx_block_start']


def test_rst_and_plain_text_heading_paths_are_structure_aware():
    rst=b'Install Guide\n=============\n\nRun the installer.\n\nTroubleshooting\n---------------\n\nCheck the port.\n'
    sections=extract_file(rst,'guide.rst').sections
    troubleshooting=next(section for section in sections if 'Check the port' in section.text)
    assert troubleshooting.title=='Troubleshooting'
    assert troubleshooting.locator['line_start']>1
    text=b'COMPANY HANDBOOK\n\nWelcome to the team.\n\nLEAVE POLICY\n\nStaff accrue 21 days of leave.\n'
    leave=next(section for section in extract_file(text,'handbook.txt').sections if '21 days' in section.text)
    assert leave.title=='LEAVE POLICY'
    assert 'Welcome to the team' not in leave.text


def test_tsv_json_and_yaml_keep_row_headers_and_key_paths():
    tsv=extract_file(b'Term\tMeaning\nATP\tEnergy carrier\n','terms.tsv').sections[0]
    assert tsv.locator['format']=='tsv' and tsv.locator['row_start']==2
    assert 'Meaning: Energy carrier' in tsv.text
    raw=b'{"policy":{"refund_days":30}}'
    json_section=next(section for section in extract_file(raw,'policy.json').sections if section.locator['key_path']=='policy.refund_days')
    assert raw.decode()[json_section.locator['section_char_start']:json_section.locator['section_char_end']]==json_section.text
    assert json_section.text=='30'
    yaml_section=next(section for section in extract_file(b'refund:\n  days: 30\n','policy.yaml').sections if section.locator['key_path']=='refund.days')
    assert yaml_section.text=='30'


def test_pdf_layout_text_splits_on_conservative_uppercase_headings(monkeypatch):
    from types import SimpleNamespace

    page=SimpleNamespace(extract_text=lambda **kwargs:'COMPANY HANDBOOK\nWelcome to the team.\n\nLEAVE POLICY\nStaff accrue 21 days of leave.')
    monkeypatch.setattr('pypdf.PdfReader',lambda _:SimpleNamespace(is_encrypted=False,pages=[page]))
    sections=extract_file(b'%PDF-synthetic','handbook.pdf').sections
    leave=next(section for section in sections if '21 days' in section.text)
    assert leave.title=='LEAVE POLICY'
    assert leave.locator['page']==1
    assert leave.locator['heading_path']==['LEAVE POLICY']


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
    from PIL import Image
    image=io.BytesIO();Image.new('RGB',(2,2),'white').save(image,format='PNG');image=image.getvalue()
    with pytest.raises(SourceError) as unavailable:extract_file(image,'notes.png')
    assert unavailable.value.code=='vision_unavailable'
    calls=[]
    snapshot=extract_file(image,'notes.png',vision=lambda data,mime:(calls.append(mime) or 'Visible source text.'))
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
    from PIL import Image
    image=io.BytesIO();Image.new('RGB',(2,2),'white').save(image,format='PNG')
    photo=client.post('/api/v1/collections/collection/materials/upload',files={'file':('photo.png',image.getvalue(),'image/png')},data={'idempotency_key':'photo-one'}).json()
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
    assert db.get(Material,revision.material_id).source_type=='txt'
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


def test_direct_drive_unsupported_and_oversized_drops_create_attention_materials(db,monkeypatch):
    from cryptography.fernet import Fernet
    monkeypatch.setattr(settings,'credentials_key',Fernet.generate_key().decode())
    db.add(ProviderConnection(learner_id='owner',provider='drive',status='connected',scopes=SCOPES,
        encrypted_credentials=encrypt_credentials({'synthetic':True})))
    collection=Collection(id='attention-drive-collection',learner_id='owner',name='Drive',
        storage_mode='drive',provisioning_state='pending')
    db.add(collection);db.commit()
    adapter=StubDrive();monkeypatch.setattr('app.ingest.drive_adapter',lambda *_:adapter)
    provision=Job(learner_id='owner',kind='drive-provision',payload={});db.add(provision);db.flush()
    provision_drive(db,provision)
    adapter.files['unsupported']={'id':'unsupported','name':'run.exe','mimeType':'application/octet-stream',
        'version':'1','parents':[collection.drive_folder_id],'size':100,'appProperties':{}}
    adapter.files['oversized']={'id':'oversized','name':'large.txt','mimeType':'text/plain',
        'version':'1','parents':[collection.drive_folder_id],'size':settings.max_upload_bytes+1,'appProperties':{}}
    poll=Job(learner_id='owner',kind='drive-sync',payload={'collection_id':collection.id});db.add(poll);db.commit()

    assert sync_drive(db,poll)['discovered']==2
    rejected=db.scalars(select(Material).where(Material.collection_id==collection.id)).all()
    assert len(rejected)==2 and all(material.status=='needs-attention' for material in rejected)
    revisions=db.scalars(select(MaterialRevision).where(MaterialRevision.collection_id==collection.id)).all()
    errors={revision.metadata_json['filename']:revision.metadata_json['error_code'] for revision in revisions}
    assert errors=={'run.exe':'unsupported_type','large.txt':'oversize'}
    assert all(revision.private_blob_key is None and revision.size==0 for revision in revisions)
    assert sync_drive(db,poll)['discovered']==0
    assert db.scalar(select(func.count(Material.id)).where(Material.collection_id==collection.id))==2


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


def test_teaching_windows_persist_as_concepts_beneath_one_selected_title(db):
    text='# One selected section\n'+' '.join(f'Fact {n} explains a distinct learning idea.' for n in range(70))
    snapshot=extract_file(text.encode(),'long-section.md')
    collection=Collection(id='collection',learner_id='owner',name='Window test');db.add(collection);db.flush()
    material=Material(id='material',learner_id='owner',collection_id=collection.id,title='Long section');db.add(material);db.flush()
    revision=MaterialRevision(id='revision',learner_id='owner',collection_id=collection.id,material_id=material.id,content_hash='window-hash');db.add(revision);db.flush()
    persist_snapshot(db,revision,snapshot)
    chunks=db.scalars(select(Chunk)).all()
    concepts=db.scalars(select(Concept).order_by(Concept.position)).all()
    citations=db.scalars(select(Citation).order_by(Citation.created_at,Citation.id)).all()
    assert len(chunks)==1 and chunks[0].title=='One selected section'
    assert len(concepts)>1
    for concept in concepts:
        citation=db.get(Citation,concept.citation_ids[0])
        assert concept.text in citation.excerpt
        assert citation.excerpt in revision.extracted_text
        assert citation.excerpt_hash==hashlib.sha256(citation.excerpt.encode()).hexdigest()
        assert chunks[0].text[citation.locator_json['excerpt_start']:citation.locator_json['excerpt_end']]==citation.excerpt


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


def test_pdf_page_manifest_and_correction_are_owned_versioned_and_resumable(db,client):
    from app.jobs import HANDLERS

    collection=Collection(id='pdf-review-collection',learner_id='owner',name='PDF review')
    db.add(collection);db.flush()
    material=Material(id='pdf-review-material',learner_id='owner',collection_id=collection.id,
                      title='Scanned source',source_type='pdf',status='needs-attention',version=4)
    db.add(material);db.flush()
    original=b'%PDF synthetic immutable original'
    original_key=LocalStorage(settings.private_storage_dir).put('owner',original)
    revision=MaterialRevision(
        id='pdf-review-revision',learner_id='owner',collection_id=collection.id,
        material_id=material.id,content_hash=hashlib.sha256(original).hexdigest(),
        mime='application/pdf',size=len(original),private_blob_key=original_key,
        metadata_json={'filename':'scanned.pdf'},
    )
    db.add(revision);db.flush();material.current_revision_id=revision.id
    staged={
        'revision_id':revision.id,'batch_index':0,'sections':[],
        'page_results':[{'page_number':1,'status':'needs-review','method':'vision',
                         'warning':'low_ocr_quality','text_chars':0,'section_count':0,
                         'chapter_path':[]}],
    }
    staged_bytes=json.dumps(staged,separators=(',',':')).encode()
    result_key=LocalStorage(settings.private_storage_dir).put('owner',staged_bytes)
    manifest={
        'version':1,'status':'needs-review','page_count':1,'batch_size':40,
        'processed_pages':1,'review_required_pages':[1],'review_required_count':1,
        'chapter_paths':[[]],'extracted_text_bytes':0,'batch_result_bytes':len(staged_bytes),
        'pages':[{'page_number':1,'status':'needs-review','method':'vision',
                  'warning':'low_ocr_quality','text_chars':0,'section_count':0,
                  'chapter_path':[]}],
        'batches':[{'index':0,'start_page':1,'end_page':1,'state':'completed',
                    'result_blob_key':result_key,'result_bytes':len(staged_bytes),
                    'extracted_text_bytes':0}],
        'obsolete_result_blob_keys':[],
    }
    revision.metadata_json={**revision.metadata_json,'ingestion_manifest':manifest}
    db.commit()

    listing=client.get(f'/api/v1/materials/{material.id}/ingestion-pages?limit=1')
    assert listing.status_code==200
    assert listing.json()['items'][0]['page_number']==1
    assert listing.json()['items'][0]['text']=='\n\n'.join([])
    assert listing.json()['items'][0]['status']=='needs-review'

    corrected=client.patch(
        f'/api/v1/materials/{material.id}/ingestion-pages/1',
        json={'expected_version':4,'text':'The page establishes the reviewed source fact.'},
    )
    assert corrected.status_code==200
    assert corrected.json()['status']=='corrected'
    assert corrected.json()['version']==5
    assert corrected.json()['material_status']=='processing'
    assert db.get(Job,corrected.json()['finalize_job_id']).kind=='ingest-pdf-finalize'
    assert 'ingest-pdf-batch' in HANDLERS and 'ingest-pdf-finalize' in HANDLERS

    reread=client.get(f'/api/v1/materials/{material.id}/ingestion-pages?limit=1').json()
    assert reread['items'][0]['text']=='The page establishes the reviewed source fact.',reread
    db.refresh(revision);db.refresh(material)
    page=revision.metadata_json['ingestion_manifest']['pages'][0]
    assert page.get('correction_hash')==hashlib.sha256(b'The page establishes the reviewed source fact.').hexdigest(),page
    assert page['status']=='corrected' and material.status=='processing'
    reread=client.get(f'/api/v1/materials/{material.id}/ingestion-pages?limit=1').json()
    assert reread['items'][0]['text']=='The page establishes the reviewed source fact.'
    assert reread['items'][0]['text_truncated'] is False
    assert LocalStorage(settings.private_storage_dir).get('owner',original_key)==original
    assert client.get('/api/v1/materials/foreign-material/ingestion-pages').status_code==404


def test_large_pdf_pipeline_resumes_40_page_batches_without_losing_global_locators(db,monkeypatch):
    from app.ingest import _start_pdf_pipeline,ingest_pdf_batch
    from app.sources.base import ExtractedSection
    from app.ingest_limits import PDF_BATCH_PAGES

    collection=Collection(id='pdf-batch-collection',learner_id='owner',name='PDF batches')
    db.add(collection);db.flush()
    material=Material(id='pdf-batch-material',learner_id='owner',collection_id=collection.id,
                      title='large.pdf',source_type='pdf',status='queued')
    db.add(material);db.flush()
    raw=b'%PDF synthetic large source'
    blob_key=LocalStorage(settings.private_storage_dir).put('owner',raw)
    revision=MaterialRevision(id='pdf-batch-revision',learner_id='owner',collection_id=collection.id,
        material_id=material.id,content_hash=hashlib.sha256(raw).hexdigest(),
        private_blob_key=blob_key,mime='application/pdf',size=len(raw),
        metadata_json={'filename':'large.pdf'})
    db.add(revision);db.flush();material.current_revision_id=revision.id
    root_job=Job(learner_id='owner',kind='ingest-material',payload={'revision_id':revision.id})
    db.add(root_job);db.commit()
    monkeypatch.setattr('app.ingest.pdf_manifest_info',lambda _: {
        'page_count':41,'chapter_paths':[[] for _ in range(41)],
    })

    started=_start_pdf_pipeline(db,revision,material,raw,'large.pdf',root_job)
    assert started['page_count']==41 and started['batch_size']==PDF_BATCH_PAGES==40
    manifest=revision.metadata_json['ingestion_manifest']
    assert [(batch['start_page'],batch['end_page']) for batch in manifest['batches']]==[(1,40),(41,41)]
    first_job=db.get(Job,manifest['batches'][0]['job_id'])
    assert first_job.kind=='ingest-pdf-batch' and first_job.state=='queued'

    def extract_batch(_data,_filename,start,end,_paths,vision=None):
        sections=[ExtractedSection(f'Page {number}',f'Page {number} source fact.','pdf',
            {'page':number,'page_start':number,'page_end':number,'heading_path':[]})
            for number in range(start,end+1)]
        pages=[{'page_number':number,'status':'text-extracted','method':'text','warning':None,
                'text_chars':len(f'Page {number} source fact.'),'section_count':1,'chapter_path':[]}
               for number in range(start,end+1)]
        return sections,pages

    monkeypatch.setattr('app.ingest.extract_pdf_page_batch',extract_batch)
    first=ingest_pdf_batch(db,first_job)
    assert first['processed_pages']==40 and first['status']=='processing'
    db.refresh(revision)
    manifest=revision.metadata_json['ingestion_manifest']
    second_job=db.get(Job,manifest['batches'][1]['job_id'])
    assert second_job.kind=='ingest-pdf-batch' and second_job.state=='queued'
    assert ingest_pdf_batch(db,second_job)['processed_pages']==41
    db.refresh(revision);db.refresh(material)
    manifest=revision.metadata_json['ingestion_manifest']
    assert manifest['status']=='finalizing' and material.status=='processing'
    finalize=db.get(Job,manifest['finalize_job_id'])
    assert finalize.kind=='ingest-pdf-finalize' and finalize.state=='queued'
    assert [page['page_number'] for page in manifest['pages']]==list(range(1,42))
    assert all(page['status']=='text-extracted' for page in manifest['pages'])


def test_pdf_manifest_accepts_1000_pages_and_rejects_page_1001(monkeypatch):
    from types import SimpleNamespace
    from app.ingest import _new_pdf_manifest
    from app.sources.local import pdf_manifest_info

    monkeypatch.setattr('pypdf.PdfReader',lambda _:SimpleNamespace(
        is_encrypted=False,pages=[None]*1000,outline=[]))
    manifest=pdf_manifest_info(b'%PDF synthetic page manifest')
    queued,pages=_new_pdf_manifest(manifest)
    assert queued['page_count']==1000 and len(pages)==1000
    assert len(queued['batches'])==25
    assert (queued['batches'][0]['start_page'],queued['batches'][0]['end_page'])==(1,40)
    assert (queued['batches'][-1]['start_page'],queued['batches'][-1]['end_page'])==(961,1000)
    assert [page['page_number'] for page in pages]==list(range(1,1001))

    monkeypatch.setattr('pypdf.PdfReader',lambda _:SimpleNamespace(
        is_encrypted=False,pages=[None]*1001,outline=[]))
    with pytest.raises(SourceError) as exceeded:
        pdf_manifest_info(b'%PDF synthetic page limit')
    assert exceeded.value.code=='pdf_page_limit'


def _seed_deletion_graph(db,collection,material_id,revision_id,content):
    material=Material(id=material_id,learner_id='owner',collection_id=collection.id,
                      title=material_id,source_type='markdown',position=0)
    db.add(material);db.flush()
    blob_key=LocalStorage(settings.private_storage_dir).put('owner',content.encode())
    revision=MaterialRevision(id=revision_id,learner_id='owner',collection_id=collection.id,
        material_id=material.id,content_hash=hashlib.sha256(content.encode()).hexdigest(),
        private_blob_key=blob_key,size=len(content),metadata_json={'filename':f'{material_id}.md'})
    db.add(revision);db.flush();material.current_revision_id=revision.id
    from app.sources.base import SourceSnapshot,ExtractedSection
    persist_snapshot(db,revision,SourceSnapshot([ExtractedSection(material_id,content,'text',{'line_start':1,'line_end':1})]))
    return material,revision,blob_key


def test_confirmed_material_deletion_removes_only_owned_history_and_rebuilds_scope(db,client):
    from datetime import timedelta
    from app.models import (ScopeItem,TitleAssessment,ProgressEvent,ReviewState)
    from app.jobs import WORKER_ID
    from app.ingest import delete_material

    db.connection().exec_driver_sql('PRAGMA foreign_keys=ON')
    collection=Collection(id='delete-collection',learner_id='owner',name='Deletion')
    db.add(collection);db.flush()
    deleted,deleted_revision,deleted_blob=_seed_deletion_graph(
        db,collection,'delete-target','delete-target-revision','Target source fact.')
    retained,retained_revision,retained_blob=_seed_deletion_graph(
        db,collection,'delete-retained','delete-retained-revision','Retained source fact.')
    deleted_chunk=db.scalar(select(Chunk).where(Chunk.material_revision_id==deleted_revision.id))
    retained_chunk=db.scalar(select(Chunk).where(Chunk.material_revision_id==retained_revision.id))
    deleted_revision_id=deleted_revision.id
    deleted_chunk_id=deleted_chunk.id
    retained_chunk_id=retained_chunk.id
    scope=ScopeRevision(id='delete-scope',learner_id='owner',collection_id=collection.id,revision_number=1,active=True)
    db.add(scope);db.flush()
    db.add_all([
        ScopeItem(learner_id='owner',scope_revision_id=scope.id,chunk_id=deleted_chunk.id,position=0),
        ScopeItem(learner_id='owner',scope_revision_id=scope.id,chunk_id=retained_chunk.id,position=1),
        TitleAssessment(learner_id='owner',chunk_id=deleted_chunk.id,scope_revision_id=scope.id,complete=True,rationale='target evidence',evidence_event_ids=['event-target'],critical_coverage={}),
        TitleAssessment(learner_id='owner',chunk_id=retained_chunk.id,scope_revision_id=scope.id,complete=True,rationale='retained evidence',evidence_event_ids=['event-retained'],critical_coverage={}),
    ])
    session=StudySession(id='delete-session',learner_id='owner',collection_id=collection.id,
                         scope_revision_id=scope.id,status='awaiting_answer',summary_json={'private':'synthetic'})
    db.add(session);db.flush()
    concept=db.scalar(select(Concept).where(Concept.chunk_id==deleted_chunk.id))
    item=SessionItem(id='delete-item',learner_id='owner',session_id=session.id,concept_id=concept.id,
                     chunk_id=deleted_chunk.id,public_question='Question',position=0)
    db.add(item);db.flush();session.current_item_id=item.id
    db.add(ProgressEvent(learner_id='owner',concept_id=concept.id,chunk_id=deleted_chunk.id,
        session_id=session.id,item_id=item.id,confidence=4,correct=True,answer='synthetic answer',
        reviewer_json={},idempotency_key='delete-progress'))
    db.add(ReviewState(learner_id='owner',chunk_id=deleted_chunk.id,stage=1,next_review_at=utcnow()))
    session_id=session.id
    db.commit()

    response=client.request('DELETE',f'/api/v1/collections/{collection.id}/materials/{deleted.id}',
        json={'expected_version':deleted.version,'confirmation':'DELETE'})
    assert response.status_code==202
    assert db.get(Material,deleted.id).status=='deleting'
    job=db.get(Job,response.json()['id'])
    job.state='running';job.lease_owner=WORKER_ID;job.lease_until=utcnow()+timedelta(minutes=5)
    db.commit()
    result=delete_material(db,job)

    assert result=={'deleted':True,'drive_files_deleted':0}
    db.expire_all()
    assert db.get(Material,deleted.id) is None and db.get(Material,retained.id) is not None
    assert db.get(MaterialRevision,deleted_revision_id) is None
    assert db.scalar(select(func.count(Chunk.id)).where(Chunk.material_revision_id==deleted_revision_id))==0
    assert db.scalar(select(func.count(Citation.id)).where(Citation.revision_id==deleted_revision_id))==0
    active=db.scalar(select(ScopeRevision).where(ScopeRevision.collection_id==collection.id,ScopeRevision.active.is_(True)))
    assert active.revision_number==2
    active_ids=set(db.scalars(select(ScopeItem.chunk_id).where(ScopeItem.scope_revision_id==active.id)))
    assert active_ids=={retained_chunk_id}
    preserved=db.scalar(select(TitleAssessment).where(TitleAssessment.scope_revision_id==active.id,TitleAssessment.chunk_id==retained_chunk_id))
    assert preserved and preserved.complete and preserved.rationale=='retained evidence'
    session=db.get(StudySession,session_id)
    assert session.status=='interrupted' and session.current_item_id is None and session.summary_json=={}
    assert db.scalar(select(func.count(SessionItem.id)).where(SessionItem.session_id==session_id))==0
    assert db.scalar(select(func.count(ProgressEvent.id)).where(ProgressEvent.session_id==session_id))==0
    assert db.scalar(select(func.count(ReviewState.id)).where(ReviewState.chunk_id==deleted_chunk_id))==0
    assert LocalStorage(settings.private_storage_dir).get('owner',retained_blob)=='Retained source fact.'.encode()
    assert not (__import__('pathlib').Path(settings.private_storage_dir)/deleted_blob).exists()
    # Crash after cleanup commit, before queue success: both completion paths replay.
    deletion_job_id=job.id
    db.expunge_all()
    assert delete_material(db,db.get(Job,deletion_job_id))=={'deleted':True}
    db.expunge_all()
    assert delete_material(db,db.get(Job,deletion_job_id))=={'deleted':True}
    assert db.get(Job,deletion_job_id).payload=={'database_deleted':True}
    assert LocalStorage(settings.private_storage_dir).get('owner',retained_blob)==b'Retained source fact.'


def test_drive_delete_failure_keeps_material_and_learning_history(db,monkeypatch):
    from datetime import timedelta
    from app.jobs import WORKER_ID,NeedsAttention
    from app.ingest import delete_material_handler

    collection=Collection(id='drive-delete-collection',learner_id='owner',name='Drive',
        storage_mode='drive',provisioning_state='ready',drive_folder_id='managed-folder',drive_root_id='root')
    db.add(collection);db.flush()
    material,revision,_=_seed_deletion_graph(db,collection,'drive-delete-target','drive-delete-revision','Remote source fact.')
    revision.origin='direct_drop';revision.storage_state='saved-to-drive';revision.drive_file_id='remote-original'
    chunk=db.scalar(select(Chunk).where(Chunk.material_revision_id==revision.id));db.commit()
    job=Job(learner_id='owner',kind='delete-material',entity_id=material.id,
        payload={'material_id':material.id,'collection_id':collection.id},state='running',
        lease_owner=WORKER_ID,lease_until=utcnow()+timedelta(minutes=5))
    db.add(job);db.commit()

    class FailedDriveDelete:
        def get_file(self,_):
            return {'id':'managed-folder','mimeType':'application/vnd.google-apps.folder','parents':['root']}
        def delete_file(self,file_id,folder_id):
            assert (file_id,folder_id)==('remote-original','managed-folder')
            raise SourceError('drive_permission','Synthetic permission failure.')

    monkeypatch.setattr('app.ingest.drive_adapter',lambda *_:FailedDriveDelete())
    with pytest.raises(NeedsAttention,match='drive_permission'):
        delete_material_handler(db,job)
    db.refresh(material);db.refresh(revision)
    assert material.status=='needs-attention'
    assert db.get(MaterialRevision,revision.id) is not None
    assert db.scalar(select(Chunk.id).where(Chunk.id==chunk.id))==chunk.id


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


def test_upload_limit_endpoint_reports_effective_server_cap(client,monkeypatch):
    monkeypatch.setattr(settings,'max_upload_bytes',5*1024*1024)
    assert client.get('/api/v1/ingestion/limits').json()=={'max_upload_bytes':5*1024*1024}
    monkeypatch.setattr(settings,'max_upload_bytes',40*1024*1024)
    assert client.get('/api/v1/ingestion/limits').json()=={'max_upload_bytes':20*1024*1024}


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


def _real_text_pdf(page_count):
    """Portable synthetic source with actual PDF font/content streams, no reader mocks."""
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, DecodedStreamObject

    writer=PdfWriter()
    font=writer._add_object(DictionaryObject({
        NameObject('/Type'):NameObject('/Font'),
        NameObject('/Subtype'):NameObject('/Type1'),
        NameObject('/BaseFont'):NameObject('/Helvetica'),
    }))
    for number in range(1,page_count+1):
        page=writer.add_blank_page(width=612,height=792)
        page[NameObject('/Resources')]=DictionaryObject({
            NameObject('/Font'):DictionaryObject({NameObject('/F1'):font}),
        })
        stream=DecodedStreamObject()
        stream.set_data((
            f'BT /F1 14 Tf 50 740 Td (LESSON {number}) Tj '
            f'0 -25 Td (Page {number} establishes that ATP carries cellular energy.) Tj ET'
        ).encode('ascii'))
        page[NameObject('/Contents')]=writer._add_object(stream)
    output=io.BytesIO();writer.write(output)
    return output.getvalue()


@pytest.mark.parametrize('page_count',[2,41])
def test_real_pdf_multipart_batches_resume_and_ground_original_pages(db,client,page_count):
    """Demo gate: actual PDF bytes survive intake, batch replay, finalize and source viewing."""
    from app.ingest import ingest_pdf_batch,finalize_pdf_material
    from pypdf import PdfReader

    db.add(Collection(id='real-pdf',learner_id='owner',name='Energy lessons'))
    db.add(Collection(id='foreign-pdf',learner_id='other',name='Other learner'))
    db.commit()
    raw=_real_text_pdf(page_count)
    arguments={'files':{'file':('energy.pdf',raw,'application/pdf')},
               'data':{'idempotency_key':f'real-pdf-{page_count}'}}
    response=client.post('/api/v1/collections/real-pdf/materials/upload',**arguments)
    assert response.status_code==202,response.text
    intake=response.json()
    assert client.post('/api/v1/collections/real-pdf/materials/upload',**arguments).json()==intake
    assert client.post('/api/v1/collections/foreign-pdf/materials/upload',**arguments).status_code==404
    started=ingest_material(db,db.get(Job,intake['job_id']))
    assert started['status']=='processing'
    revision=db.get(MaterialRevision,intake['revision_id'])
    assert revision.content_hash==hashlib.sha256(raw).hexdigest()
    assert client.get(f"/api/v1/material-revisions/{revision.id}/original").content==raw

    # Commit/reload the DB state between every batch, as after a worker restart.
    # Replay the first committed batch: extraction must not create duplicate jobs/results.
    while True:
        db.commit();db.expunge_all()
        revision=db.get(MaterialRevision,intake['revision_id'])
        manifest=revision.metadata_json['ingestion_manifest']
        pending=next((batch for batch in manifest['batches'] if batch['state']!='completed'),None)
        if pending is None:
            break
        job=db.get(Job,pending['job_id'])
        result=ingest_pdf_batch(db,job)
        assert result['review_required_count']==0
        job_count=db.scalar(select(func.count(Job.id)))
        replay=ingest_pdf_batch(db,job)
        assert replay['status']=='completed'
        assert db.scalar(select(func.count(Job.id)))==job_count
    assert manifest['processed_pages']==page_count
    assert [page['page_number'] for page in manifest['pages']]==list(range(1,page_count+1))
    assert all(page['method']=='text' for page in manifest['pages'])
    finalize_id=manifest['finalize_job_id']
    assert finalize_pdf_material(db,db.get(Job,finalize_id))['status']=='ready'
    db.expunge_all()
    assert client.get(f"/api/v1/materials/{intake['material_id']}").json()['status']=='ready'
    outline=client.get('/api/v1/collections/real-pdf/outline')
    assert outline.status_code==200,outline.text
    chunks=db.scalars(select(Chunk).where(Chunk.material_revision_id==intake['revision_id'])).all()
    assert len(chunks)==page_count
    assert {chunk.title for chunk in chunks}=={f'LESSON {number}' for number in range(1,page_count+1)}
    concepts=db.scalars(select(Concept).where(Concept.chunk_id.in_([chunk.id for chunk in chunks]))).all()
    assert concepts
    pages=PdfReader(io.BytesIO(raw)).pages
    for concept in concepts:
        citation=db.get(Citation,concept.citation_ids[0])
        resolved=client.get(f'/api/v1/citations/{citation.id}')
        assert resolved.status_code==200,resolved.text
        source=resolved.json()
        assert source['revision_id']==intake['revision_id']
        assert source['excerpt'] in pages[source['locator']['page']-1].extract_text()
        assert concept.text in source['excerpt']
        assert client.get(source['viewer_url']).content==raw
    # Crash after cleanup commit, before queue success: restart/replay is safe.
    db.expunge_all()
    assert finalize_pdf_material(db,db.get(Job,finalize_id))['status']=='ready'
    assert db.scalar(select(func.count(Chunk.id)))==page_count
    assert client.get(f"/api/v1/material-revisions/{intake['revision_id']}/original").content==raw
