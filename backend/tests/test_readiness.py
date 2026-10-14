"""Connected readiness cannot hide missing authentication or Drive setup."""
import json
from pathlib import Path
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine,text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from cryptography.fernet import Fernet
import pytest
from app.db import Base,utcnow
from app.models import WorkerHeartbeat
from app.settings import settings
from app import main

@pytest.fixture
def ready_env(monkeypatch):
    engine=create_engine('sqlite://',poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory=sessionmaker(engine,expire_on_commit=False)
    with factory() as db:
        db.execute(text('CREATE TABLE alembic_version (version_num VARCHAR(32))'))
        for head in ScriptDirectory(str(Path(__file__).resolve().parents[1] / "migrations")).get_heads():
            db.execute(text("INSERT INTO alembic_version VALUES (:head)"), {"head": head})
        db.add(WorkerHeartbeat(worker_id='synthetic-worker',checked_at=utcnow()));db.commit()
    monkeypatch.setattr(main,'SessionLocal',factory)
    values={'app_mode':'live','api_key':'synthetic-private-api','model':'synthetic-model',
        'oidc_issuer':'https://accounts.google.com','oidc_client_id':'synthetic-id','oidc_client_secret':'synthetic-private-google',
        'session_secret':'synthetic-private-session-'*3,'credentials_key':Fernet.generate_key().decode(),
        'drive_client_id':'synthetic-id','drive_client_secret':'synthetic-private-google',
        'public_url':'http://localhost:3000','drive_redirect_uri':'http://localhost:3000/api/v1/connections/drive/callback'}
    for name,value in values.items():monkeypatch.setattr(settings,name,value)
    yield values
    engine.dispose()


def test_live_readiness_requires_sign_in_and_reports_unverified_drive(ready_env,monkeypatch):
    response=main.ready();assert response.status_code==200
    data=json.loads(response.body)
    assert data['dependencies']['oidc']=='configured-unverified'
    assert data['dependencies']['drive']=='configured-unverified'
    for field in ('oidc_client_id','oidc_client_secret'):
        monkeypatch.setattr(settings,field,None)
        response=main.ready();assert response.status_code==503
        assert json.loads(response.body)['dependencies']['oidc']=='unconfigured'
        monkeypatch.setattr(settings,field,ready_env[field])


def test_readiness_reports_bad_drive_without_claiming_provider_success(ready_env,monkeypatch):
    monkeypatch.setattr(settings,'drive_redirect_uri','http://127.0.0.1:3000/api/v1/connections/drive/callback')
    response=main.ready();data=json.loads(response.body)
    assert data['dependencies']['drive']=='unconfigured'
    assert ready_env['api_key'] not in response.body.decode()
    assert ready_env['credentials_key'] not in response.body.decode()


def test_test_mode_is_offline_and_missing_model_blocks_live(ready_env,monkeypatch):
    monkeypatch.setattr(settings,'api_key',None)
    assert main.ready().status_code==503
    monkeypatch.setattr(settings,'app_mode','test')
    response=main.ready();assert response.status_code==200
    assert json.loads(response.body)['dependencies']['model']=='offline-demo'


@pytest.mark.parametrize('revision', ['0002_durable_guards', 'unknown_future_revision'])
def test_readiness_rejects_database_that_does_not_match_shipped_heads(ready_env, revision):
    with main.SessionLocal() as db:
        db.execute(text('UPDATE alembic_version SET version_num=:revision'), {'revision': revision})
        db.commit()
    response = main.ready()
    assert response.status_code == 503
    assert json.loads(response.body)['dependencies']['database'] == 'migration-required'


def test_readiness_handles_a_later_release_and_all_migration_heads(ready_env, monkeypatch):
    monkeypatch.setattr(main, 'migration_heads', lambda: frozenset({'future_a', 'future_b'}))
    with main.SessionLocal() as db:
        db.execute(text('DELETE FROM alembic_version'))
        db.execute(text('INSERT INTO alembic_version VALUES (:head)'), [{'head': 'future_a'}, {'head': 'future_b'}])
        db.commit()
    assert main.ready().status_code == 200
    with main.SessionLocal() as db:
        db.execute(text("DELETE FROM alembic_version WHERE version_num='future_b'"))
        db.commit()
    assert main.ready().status_code == 503


def test_fresh_alembic_upgrade_is_ready_with_a_live_worker(tmp_path, monkeypatch):
    from test_migrations import migrate
    url = f"sqlite:///{tmp_path / 'fresh-readiness.db'}"
    migrate(url)
    engine = create_engine(url)
    factory = sessionmaker(engine, expire_on_commit=False)
    try:
        with factory() as db:
            db.add(WorkerHeartbeat(worker_id='synthetic-fresh-worker', checked_at=utcnow()))
            db.commit()
        monkeypatch.setattr(main, 'SessionLocal', factory)
        monkeypatch.setattr(settings, 'app_mode', 'test')
        response = main.ready()
        assert response.status_code == 200
        assert json.loads(response.body)['dependencies']['database'] == 'ready'
    finally:
        engine.dispose()
