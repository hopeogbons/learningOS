"""Alembic creates/upgrades/downgrades actual engines, not metadata create_all."""
import os
import subprocess
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlencode
import pytest
from sqlalchemy import create_engine, inspect, text

BACKEND=Path(__file__).resolve().parents[1]

def migrate(url, revision="head"):
    environment={**os.environ,"DATABASE_URL":url,"APP_MODE":"test"}
    subprocess.run([str(BACKEND/".venv/bin/alembic"),"upgrade" if revision=="head" else "downgrade",revision],cwd=BACKEND,env=environment,check=True,capture_output=True,text=True)

def verify_constraints(url):
    engine=create_engine(url)
    info=inspect(engine)
    assert {"learners","collections","scope_revisions","scope_items","jobs","auth_sessions","source_write_receipts"} <= set(info.get_table_names())
    assert any(i["name"]=="uq_active_scope" and i["unique"] for i in info.get_indexes("scope_revisions"))
    assert any(c["column_names"]==["learner_id","idempotency_key"] for c in info.get_unique_constraints("jobs"))
    assert info.get_foreign_keys("scope_items")
    with engine.connect() as conn:assert conn.execute(text("SELECT version_num FROM alembic_version")).scalar()=="0002_durable_guards"
    engine.dispose()

def test_sqlite_fresh_upgrade_rollback_reupgrade(tmp_path):
    url=f"sqlite:///{tmp_path/'fresh.db'}"
    migrate(url);verify_constraints(url);migrate(url,"base")
    engine=create_engine(url)
    assert set(inspect(engine).get_table_names())=={"alembic_version"}
    engine.dispose();migrate(url);verify_constraints(url)

def test_postgresql_fresh_upgrade_rollback_reupgrade():
    base_url=os.getenv("TEST_POSTGRES_URL")
    if not base_url:pytest.skip("TEST_POSTGRES_URL not supplied; real PostgreSQL gate stays unrun")
    schema="core_test_"+uuid4().hex
    admin=create_engine(base_url)
    with admin.begin() as conn:conn.execute(text(f'CREATE SCHEMA "{schema}"'))
    url=base_url+("&" if "?" in base_url else "?")+urlencode({"options":"-csearch_path="+schema})
    try:
        migrate(url);verify_constraints(url);migrate(url,"base")
        engine=create_engine(url)
        assert set(inspect(engine).get_table_names())=={"alembic_version"}
        engine.dispose();migrate(url);verify_constraints(url)
    finally:
        with admin.begin() as conn:conn.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        admin.dispose()
