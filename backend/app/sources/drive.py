"""Runtime Google Drive REST adapter; never borrows a developer connector token."""
import json
import re
import time
from urllib.parse import urlsplit
import httpx
from cryptography.fernet import Fernet, InvalidToken
from ..settings import settings
from .base import SourceError

WRITE_SCOPE = 'https://www.googleapis.com/auth/drive.file'
READ_SCOPE = 'https://www.googleapis.com/auth/drive.readonly'
SCOPES = [WRITE_SCOPE, READ_SCOPE]
FILE_FIELDS = 'id,name,mimeType,version,md5Checksum,size,parents,trashed,appProperties,capabilities(canAddChildren,canDownload)'


def connection_setup_state():
    """Report connectability without exposing values or claiming provider access."""
    if settings.app_mode in {'demo', 'test'}:
        return 'demo'
    if not all((settings.drive_client_id, settings.drive_client_secret,
                settings.credentials_key, settings.drive_redirect_uri)):
        return 'unconfigured'
    try:
        Fernet(settings.credentials_key.encode())
        origin = urlsplit(settings.public_url)
        if origin.port is not None and not 1 <= origin.port <= 65535:
            return 'unconfigured'
        if (not origin.hostname or origin.username or origin.password or origin.query
                or origin.fragment or origin.path not in {'', '/'}):
            return 'unconfigured'
        if origin.scheme != 'https' and not (origin.scheme == 'http' and origin.hostname in {'localhost', '127.0.0.1', '::1'}):
            return 'unconfigured'
        if settings.drive_redirect_uri != settings.public_url.rstrip('/') + '/api/v1/connections/drive/callback':
            return 'unconfigured'
    except (ValueError, TypeError):
        return 'unconfigured'
    return 'ready'


def encrypt_credentials(value):
    if not settings.credentials_key: raise SourceError('credentials_key_missing', 'Secure credential storage is not configured.')
    return Fernet(settings.credentials_key.encode()).encrypt(json.dumps(value).encode()).decode()


def decrypt_credentials(value):
    if not settings.credentials_key: raise SourceError('credentials_key_missing', 'Secure credential storage is not configured.')
    try: return json.loads(Fernet(settings.credentials_key.encode()).decrypt(value.encode()))
    except (InvalidToken, ValueError) as exc: raise SourceError('credentials_invalid', 'Reconnect Drive to restore secure access.') from exc


class DriveAdapter:
    def __init__(self, credentials, persist_credentials=None, client=None):
        self.credentials = credentials; self.persist_credentials = persist_credentials
        self.client = client or httpx.Client(timeout=20, follow_redirects=False)
    def _token(self):
        if self.credentials.get('expires_at', 0) < time.time()+60:
            if not self.credentials.get('refresh_token'):
                raise SourceError('drive_reconnect', 'Reconnect Drive; its authorization has expired.')
            response = self.client.post('https://oauth2.googleapis.com/token', data={'client_id': settings.drive_client_id, 'client_secret': settings.drive_client_secret, 'refresh_token': self.credentials['refresh_token'], 'grant_type':'refresh_token'})
            if response.status_code != 200: raise SourceError('drive_reconnect', 'Drive authorization could not be refreshed.')
            body = response.json(); self.credentials.update(body); self.credentials['expires_at'] = time.time()+body.get('expires_in',3600)
            if self.persist_credentials: self.persist_credentials(self.credentials)
        return self.credentials['access_token']
    def request(self, method, url, **kwargs):
        allowed_status=kwargs.pop('allowed_status', set())
        headers = kwargs.pop('headers', {}); headers['Authorization'] = f'Bearer {self._token()}'
        try: response = self.client.request(method, url, headers=headers, **kwargs)
        except httpx.HTTPError as exc: raise SourceError('drive_network', 'Drive is temporarily unavailable.',True) from exc
        if response.status_code >= 400 and response.status_code not in allowed_status:
            code = {401:'drive_reconnect',403:'drive_permission',404:'drive_folder_missing',429:'drive_quota'}.get(response.status_code,'drive_unavailable')
            raise SourceError(code, 'Drive did not confirm this operation. Reconnect or retry when available.',response.status_code in {429,500,502,503,504})
        return response
    def list_files(self, folder_id=None, identity=None):
        terms = ['trashed = false']
        if folder_id: terms.append(f"'{self._safe_id(folder_id)}' in parents")
        if identity: terms.append("appProperties has { key='learningos_identity' and value='"+self._safe_id(identity)+"' }")
        files=[]; page=None
        while True:
            params={'q':' and '.join(terms),'fields':f'nextPageToken,files({FILE_FIELDS})','pageSize':100}
            if page: params['pageToken']=page
            body=self.request('GET','https://www.googleapis.com/drive/v3/files',params=params).json(); files.extend(body.get('files',[])); page=body.get('nextPageToken')
            if len(files)>2000: raise SourceError('drive_scan_limit','Folder exceeds the bounded 2,000-file scan.')
            if not page: return files
    @staticmethod
    def _safe_id(value):
        if not re.fullmatch(r'[A-Za-z0-9_:\-]{1,255}',value): raise SourceError('invalid_drive_id','Invalid bound Drive identity.')
        return value
    def get_file(self,file_id):
        return self.request('GET',f'https://www.googleapis.com/drive/v3/files/{self._safe_id(file_id)}',params={'fields':FILE_FIELDS}).json()
    def ensure_folder(self, identity, name, parent=None, existing_id=None):
        if existing_id:
            folder=self.get_file(existing_id)
            if folder.get('trashed') or folder.get('mimeType')!='application/vnd.google-apps.folder' or (parent and parent not in folder.get('parents',[])):
                raise SourceError('drive_folder_missing','The bound folder moved or was removed; relink explicitly.')
            if not folder.get('capabilities',{}).get('canAddChildren',False): raise SourceError('drive_permission','The bound folder is not writable.')
            return folder
        found=self.list_files(parent,identity)
        if len(found)>1: raise SourceError('drive_identity_conflict','Multiple managed identities exist; reconcile before continuing.')
        if found:
            return self.ensure_folder(identity,name,parent,found[0]['id'])
        body={'name':name,'mimeType':'application/vnd.google-apps.folder','appProperties':{'learningos_identity':identity,'learningos_schema':'1'}}
        if parent: body['parents']=[parent]
        return self.request('POST','https://www.googleapis.com/drive/v3/files',json=body,params={'fields':FILE_FIELDS}).json()
    def upload(self, folder_id, identity, filename, data, mime, receipt, persist_receipt):
        # External success is reconciled by appProperties even after a lost DB commit.
        found=self.list_files(folder_id,identity)
        if len(found)>1: raise SourceError('drive_identity_conflict','Duplicate upload identities require attention.')
        if found: return found[0]
        folder=self.get_file(folder_id)
        if folder.get('trashed') or not folder.get('capabilities',{}).get('canAddChildren',False): raise SourceError('drive_permission','The selected Collection folder is not writable.')
        location=receipt.get('resumable_url')
        offset=0
        if location:
            self._validate_upload_url(location)
            probe=self.request('PUT',location,headers={'Content-Length':'0','Content-Range':f'bytes */{len(data)}'},content=b'',allowed_status={404,410})
            if probe.status_code in {200,201}: return probe.json()
            if probe.status_code==308: offset=int(probe.headers.get('Range','bytes=0--1').split('-')[-1])+1
            else: location=None
        if not location:
            body={'name':filename,'parents':[folder_id],'appProperties':{'learningos_identity':identity,'learningos_schema':'1','learningos_origin':'ui'}}
            response=self.request('POST','https://www.googleapis.com/upload/drive/v3/files',params={'uploadType':'resumable','fields':FILE_FIELDS},json=body,headers={'X-Upload-Content-Type':mime,'X-Upload-Content-Length':str(len(data))})
            location=response.headers.get('Location'); self._validate_upload_url(location)
            receipt={**receipt,'resumable_url':location}; persist_receipt(receipt)
        while offset<len(data):
            end=min(offset+1024*1024,len(data))-1
            response=self.request('PUT',location,content=data[offset:end+1],headers={'Content-Type':mime,'Content-Length':str(end-offset+1),'Content-Range':f'bytes {offset}-{end}/{len(data)}'})
            if response.status_code in {200,201}: return response.json()
            if response.status_code!=308: raise SourceError('drive_upload_pending','Drive upload is not confirmed.',True)
            offset=int(response.headers.get('Range',f'bytes=0-{end}').split('-')[-1])+1
        raise SourceError('drive_upload_pending','Drive upload awaits final confirmation.',True)
    @staticmethod
    def _validate_upload_url(url):
        if not url or urlsplit(url).scheme!='https' or urlsplit(url).hostname!='www.googleapis.com' or not urlsplit(url).path.startswith('/upload/drive/'):
            raise SourceError('drive_upload_url','Drive returned an invalid upload destination.')
    def download(self,file_id,max_bytes):
        token=self._token()
        try:
            with self.client.stream('GET',f'https://www.googleapis.com/drive/v3/files/{self._safe_id(file_id)}',params={'alt':'media'},headers={'Authorization':f'Bearer {token}'}) as response:
                if response.status_code!=200: raise SourceError('drive_download','Drive source download was not confirmed.',response.status_code>=500)
                parts=[];total=0;started=time.monotonic()
                for chunk in response.iter_bytes(65536):
                    total+=len(chunk)
                    if total>max_bytes:raise SourceError('oversize','Drive source exceeds the upload limit.')
                    if time.monotonic()-started>45:raise SourceError('drive_timeout','Drive source download exceeded its time budget.',True)
                    parts.append(chunk)
                return b''.join(parts)
        except httpx.HTTPError as exc:raise SourceError('drive_network','Drive source download failed.',True) from exc
    def revoke(self):
        token=self.credentials.get('refresh_token') or self.credentials.get('access_token')
        response=self.client.post('https://oauth2.googleapis.com/revoke',data={'token':token})
        return response.status_code==200


def revoke_connection(connection):
    """Delete local access first, then attempt provider revocation without token logs."""
    encrypted=connection.encrypted_credentials
    connection.encrypted_credentials=None
    connection.status='disconnected'
    if not encrypted:return True
    try:return DriveAdapter(decrypt_credentials(encrypted)).revoke()
    except (SourceError,httpx.HTTPError):return False
