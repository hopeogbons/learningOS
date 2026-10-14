"""Initializer completes missing setup without rotating existing connection keys."""
import importlib.util
from pathlib import Path
import pytest
from cryptography.fernet import Fernet

SPEC=importlib.util.spec_from_file_location('local_initializer',Path(__file__).resolve().parents[2]/'scripts/prepare_localhost.py')
MODULE=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MODULE)


def skeleton(tmp_path):
    source=Path(__file__).resolve().parents[2]/'deploy/localhost.env.example'
    (tmp_path/'deploy').mkdir();(tmp_path/'deploy/localhost.env.example').write_text(source.read_text())
    return tmp_path


def parse(path):
    return dict(line.split('=',1) for line in path.read_text().splitlines() if '=' in line and not line.startswith('#'))


def test_create_repeat_and_partial_config_preserve_private_keys(tmp_path):
    root=skeleton(tmp_path);path=MODULE.prepare(root,docker=True);first=path.read_bytes();values=parse(path)
    Fernet(values['TOKEN_ENCRYPTION_KEY'].encode())
    assert len(values['SESSION_SIGNING_KEY'])>=32 and path.stat().st_mode&0o077==0
    assert MODULE.prepare(root,docker=True).read_bytes()==first
    path.write_text('LEARNING_OS_API_KEY=synthetic-preserved-key\nTOKEN_ENCRYPTION_KEY='+values['TOKEN_ENCRYPTION_KEY']+'\n')
    MODULE.prepare(root,docker=True);updated=parse(path)
    assert updated['LEARNING_OS_API_KEY']=='synthetic-preserved-key'
    assert updated['TOKEN_ENCRYPTION_KEY']==values['TOKEN_ENCRYPTION_KEY']
    assert updated['OIDC_ISSUER']=='https://accounts.google.com'
    assert updated['DRIVE_REDIRECT_URI']=='http://127.0.0.1:3000/api/v1/connections/drive/callback'


def test_empty_settings_and_legacy_keys_are_repaired_without_rotation(tmp_path):
    root=skeleton(tmp_path);runtime=root/'.runtime/localhost';runtime.mkdir(parents=True);path=runtime/'localhost.env';path.write_text('')
    MODULE.prepare(root,docker=True);assert parse(path)['SESSION_SIGNING_KEY']
    legacy=Fernet.generate_key().decode();path.write_text('CREDENTIALS_KEY='+legacy+'\nSESSION_SECRET=synthetic-old-session-key\n')
    MODULE.prepare(root,docker=True);values=parse(path)
    assert values['TOKEN_ENCRYPTION_KEY']==legacy and values['SESSION_SIGNING_KEY']=='synthetic-old-session-key'


def test_initializer_refuses_symlink_without_changing_target(tmp_path):
    root=skeleton(tmp_path);runtime=root/'.runtime/localhost';runtime.mkdir(parents=True)
    other=root/'preserved.env';other.write_text('synthetic-preserved')
    (runtime/'localhost.env').symlink_to(other)
    with pytest.raises(RuntimeError,match='regular file'):MODULE.prepare(root,docker=True)
    assert other.read_text()=='synthetic-preserved'
