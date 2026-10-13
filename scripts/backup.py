#!/usr/bin/env python3
"""Quiesced database/private object backups and isolated, non-destructive restore proof.

Never prints credential-bearing connection strings or learner rows. Backups themselves
contain private data: keep them outside tracked files, encrypt at rest, and expire them
according to the deployment's retention/deletion policy.
"""
import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import tempfile
from urllib.parse import unquote, urlparse

REPO = Path(__file__).resolve().parents[1]

def sha(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()

def sqlite_path(url):
    if not url.startswith('sqlite:///'):
        raise ValueError('Expected a file-backed SQLite URL')
    return Path(url.removeprefix('sqlite:///')).resolve()

def signatures(connection, dialect):
    if dialect == 'sqlite':
        tables = [row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
    else:
        tables = [row[0] for row in connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")]
    result = {}
    for table in tables:
        quoted = '"' + table.replace('"', '""') + '"'
        # Sorted row digests compare IDs, source/citation hashes, history and schedule,
        # without retaining row values in operational evidence.
        row_hashes = sorted(hashlib.sha256(json.dumps(list(row), default=str, ensure_ascii=False, separators=(',', ':')).encode()).hexdigest() for row in connection.execute(f'SELECT * FROM {quoted}'))
        result[table] = {'count': len(row_hashes), 'rows_sha256': hashlib.sha256('\n'.join(row_hashes).encode()).hexdigest()}
    return result

def pg_environment(url):
    parsed = urlparse(url.replace('postgresql+psycopg://', 'postgresql://', 1))
    if parsed.scheme != 'postgresql' or not parsed.hostname or not parsed.path.strip('/'):
        raise ValueError('Expected an explicit PostgreSQL host/database URL')
    env = os.environ.copy()
    env.update(PGHOST=parsed.hostname, PGPORT=str(parsed.port or 5432), PGDATABASE=unquote(parsed.path.strip('/')), PGUSER=unquote(parsed.username or ''))
    if parsed.password is not None:
        env['PGPASSWORD'] = unquote(parsed.password)
    from urllib.parse import parse_qs
    query = parse_qs(parsed.query)
    if 'sslmode' in query:
        env['PGSSLMODE'] = query['sslmode'][0]
    return env

def pg_connect(url):
    import psycopg
    return psycopg.connect(url.replace('postgresql+psycopg://', 'postgresql://', 1))

def copy_local_objects(root, destination):
    root = root.resolve()
    if not root.exists():
        raise ValueError('Configured private object directory is missing')
    for source in root.rglob('*'):
        if source.is_symlink():
            raise ValueError('Private object symlinks are not backed up')
        if source.is_file():
            target = destination / source.relative_to(root)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)

def backup(args):
    if not args.quiesced:
        raise ValueError('Stop API/worker writes first, then explicitly pass --quiesced; DB and objects need a common consistency boundary')
    destination = args.output.resolve()
    if destination.exists():
        raise ValueError('Output must be a new directory; existing backups are never overwritten')
    runtime = Path(os.getenv('LEARNING_OS_RUNTIME_DIR', REPO / '.runtime')).resolve()
    if destination.is_relative_to(REPO) and not destination.is_relative_to(runtime):
        raise ValueError('Private backups within the checkout must be under the ignored runtime directory')
    destination.mkdir(parents=True, mode=0o700)
    database_url = os.environ['DATABASE_URL']
    if database_url.startswith('sqlite:///'):
        source_path = sqlite_path(database_url)
        if not source_path.is_file():
            raise ValueError('Configured source database is missing')
        with closing(sqlite3.connect(f'file:{source_path}?mode=ro', uri=True)) as source, closing(sqlite3.connect(destination / 'database.sqlite3')) as target:
            source.backup(target)
            # Make the artifact self-contained; no disappearing WAL/SHM sidecars.
            target.execute('PRAGMA wal_checkpoint(TRUNCATE)')
            target.execute('PRAGMA journal_mode=DELETE')
            target.commit()
            expected = signatures(target, 'sqlite')
        dialect = 'sqlite'
    elif database_url.startswith('postgresql'):
        if not shutil.which('pg_dump'):
            raise ValueError('Install a matching PostgreSQL pg_dump client before PostgreSQL backup')
        with pg_connect(database_url) as source:
            expected = signatures(source, 'postgresql')
        subprocess.run(['pg_dump', '--format=custom', '--no-owner', '--file', str(destination / 'database.dump')], env=pg_environment(database_url), check=True)
        dialect = 'postgresql'
    else:
        raise ValueError('Unsupported backup database')
    objects = destination / 'objects'
    objects.mkdir()
    bucket = os.getenv('STORAGE_BUCKET') or os.getenv('S3_BUCKET')
    if bucket:
        import boto3
        client = boto3.client('s3', endpoint_url=os.getenv('STORAGE_ENDPOINT') or os.getenv('S3_ENDPOINT_URL'), region_name=os.getenv('STORAGE_REGION') or os.getenv('AWS_DEFAULT_REGION'), aws_access_key_id=os.getenv('STORAGE_ACCESS_KEY') or None, aws_secret_access_key=os.getenv('STORAGE_SECRET_KEY') or None)
        for page in client.get_paginator('list_objects_v2').paginate(Bucket=bucket):
            for obj in page.get('Contents', []):
                key = obj['Key']
                # Encode key rather than trusting provider names as local paths.
                target = objects / hashlib.sha256(key.encode()).hexdigest()
                client.download_file(bucket, key, str(target))
                with (destination / 'object-keys.jsonl').open('a') as stream:
                    stream.write(json.dumps({'key': key, 'file': target.name}) + '\n')
        object_mode = 's3-export'
    else:
        copy_local_objects(Path(os.environ['PRIVATE_STORAGE_DIR']), objects)
        object_mode = 'private-local'
    files = {str(path.relative_to(destination)): sha(path) for path in destination.rglob('*') if path.is_file()}
    manifest = {'schema_version': 1, 'created_at': datetime.now(timezone.utc).isoformat(), 'database': dialect, 'quiesced': True, 'object_mode': object_mode, 'tables': expected, 'files': files}
    (destination / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f'Private backup verified: {len(expected)} tables; {len(files)} hashed files. Keep backup encrypted and excluded from Git.')

def restore_check(args):
    backup_dir = args.backup.resolve()
    manifest = json.loads((backup_dir / 'manifest.json').read_text())
    if manifest.get('schema_version') != 1 or not manifest.get('quiesced'):
        raise ValueError('Unknown or non-quiesced backup manifest')
    for name, expected in manifest['files'].items():
        path = backup_dir / name
        if path.is_symlink() or not path.resolve().is_relative_to(backup_dir) or not path.is_file() or sha(path) != expected:
            raise ValueError('Backup file integrity verification failed')
    if manifest['database'] == 'sqlite':
        with tempfile.TemporaryDirectory(prefix='learningos-isolated-restore-') as directory:
            target = Path(directory) / 'restored.sqlite3'
            shutil.copyfile(backup_dir / 'database.sqlite3', target)
            with closing(sqlite3.connect(target)) as connection:
                if connection.execute('PRAGMA quick_check').fetchone()[0] != 'ok' or list(connection.execute('PRAGMA foreign_key_check')):
                    raise ValueError('Restored database integrity/foreign keys failed')
                actual = signatures(connection, 'sqlite')
    elif manifest['database'] == 'postgresql':
        target_url = os.getenv('RESTORE_DATABASE_URL', '')
        target = pg_environment(target_url)
        if not target['PGDATABASE'].endswith('_restore_check') or target_url == os.environ.get('DATABASE_URL'):
            raise ValueError('Use a separate pre-created empty database named *_restore_check via RESTORE_DATABASE_URL; production restore is never automatic')
        if not shutil.which('pg_restore'):
            raise ValueError('Install the matching PostgreSQL pg_restore client')
        with pg_connect(target_url) as connection:
            if list(connection.execute("SELECT tablename FROM pg_tables WHERE schemaname='public'")):
                raise ValueError('Restore target must have no existing public tables')
        subprocess.run(['pg_restore', '--exit-on-error', '--no-owner', '--no-acl', '--dbname', target['PGDATABASE'], str(backup_dir / 'database.dump')], env=target, check=True)
        with pg_connect(target_url) as connection:
            actual = signatures(connection, 'postgresql')
    else:
        raise ValueError('Unsupported backup dialect')
    if actual != manifest['tables']:
        raise ValueError('Restored table counts/content signatures differ')
    print(f'Isolated restore passed: {len(actual)} table counts/content signatures and all private-object hashes match. No live object bucket was changed.')

def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    create = commands.add_parser('backup')
    create.add_argument('--output', required=True, type=Path)
    create.add_argument('--quiesced', action='store_true')
    restore = commands.add_parser('restore-check')
    restore.add_argument('backup', type=Path)
    args = parser.parse_args()
    try:
        (backup if args.command == 'backup' else restore_check)(args)
    except (ValueError, FileNotFoundError, KeyError) as error:
        parser.exit(1, f'{error}\n')
    except Exception:
        # Driver/provider exceptions may contain credential-bearing DSNs/keys.
        parser.exit(1, 'Backup/restore operation failed. Inspect securely; connection strings and private rows are deliberately omitted.\n')

if __name__ == '__main__':
    main()
