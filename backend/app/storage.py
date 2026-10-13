"""Private tenant-scoped originals. Keys are opaque, never caller paths."""
import hashlib
import os
import tempfile
from pathlib import Path
from .settings import settings
from .sources.base import SourceError


def validate_key(key, learner_id):
    if not key.startswith(f'{learner_id}/') or '..' in key or key.startswith('/') or '\\' in key:
        raise SourceError('storage_forbidden', 'The private object is not owned by this learner.')


class LocalStorage:
    def __init__(self, root=None):
        self.root = Path(root or settings.private_storage_dir).resolve()
        self.root.mkdir(parents=True, exist_ok=True, mode=0o700)
    def put(self, learner_id, data, filename='source'):
        key = f'{learner_id}/{hashlib.sha256(data).hexdigest()}'
        validate_key(key, learner_id)
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root): raise SourceError('storage_forbidden', 'Invalid private object key.')
        path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not path.exists():
            descriptor, temporary_name = tempfile.mkstemp(prefix='.source-', suffix='.tmp', dir=path.parent)
            temporary=Path(temporary_name)
            try:
                with os.fdopen(descriptor, 'wb') as stream:
                    stream.write(data); stream.flush(); os.fsync(stream.fileno())
                os.replace(temporary, path)
            finally:
                temporary.unlink(missing_ok=True)
        return key
    def get(self, learner_id, key):
        validate_key(key, learner_id)
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root): raise SourceError('storage_forbidden', 'Invalid private object key.')
        return path.read_bytes()
    def delete(self, learner_id, key):
        validate_key(key, learner_id)
        path = (self.root / key).resolve()
        if not path.is_relative_to(self.root): raise SourceError('storage_forbidden', 'Invalid private object key.')
        path.unlink(missing_ok=True)


class S3Storage:
    def __init__(self):
        import boto3
        options={'endpoint_url':settings.s3_endpoint_url}
        for option,variable in [('region_name','STORAGE_REGION'),('aws_access_key_id','STORAGE_ACCESS_KEY'),('aws_secret_access_key','STORAGE_SECRET_KEY')]:
            if os.getenv(variable):options[option]=os.getenv(variable)
        self.client = boto3.client('s3', **options)
        self.bucket = settings.s3_bucket
    def put(self, learner_id, data, filename='source'):
        key = f'{learner_id}/{hashlib.sha256(data).hexdigest()}'
        validate_key(key, learner_id)
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ServerSideEncryption='AES256', ContentType='application/octet-stream')
        return key
    def get(self, learner_id, key):
        validate_key(key, learner_id)
        return self.client.get_object(Bucket=self.bucket, Key=key)['Body'].read()
    def delete(self, learner_id, key):
        validate_key(key, learner_id)
        self.client.delete_object(Bucket=self.bucket, Key=key)


def get_storage():
    return S3Storage() if settings.s3_bucket else LocalStorage()
