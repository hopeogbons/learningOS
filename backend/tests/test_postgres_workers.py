"""Real separate PostgreSQL workers and expired leases across provider checkpoints."""
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlencode
import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker
from app.models import Learner, Job, Notification
from app.db import utcnow

BACKEND=Path(__file__).resolve().parents[1]

@pytest.fixture
def pg():
    base=os.getenv("TEST_POSTGRES_URL")
    if not base:pytest.skip("TEST_POSTGRES_URL required for real multiworker test")
    admin=create_engine(base)
    schema="workers_test_"+uuid4().hex
    with admin.begin() as db:db.execute(text(f'CREATE SCHEMA "{schema}"'))
    url=base+("&" if "?" in base else "?")+urlencode({"options":"-csearch_path="+schema})
    environment={**os.environ,"DATABASE_URL":url,"APP_MODE":"test"}
    subprocess.run([str(BACKEND/".venv/bin/alembic"),"upgrade","head"],cwd=BACKEND,env=environment,check=True,capture_output=True)
    engine=create_engine(url);factory=sessionmaker(engine,expire_on_commit=False)
    uid=str(uuid4())
    with factory() as db:db.add(Learner(id=uid));db.commit()
    yield environment,factory,uid
    engine.dispose()
    with admin.begin() as db:db.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
    admin.dispose()

PROGRAM='''
import os,time
from pathlib import Path
from datetime import timedelta
from app import jobs
from app.db import utcnow
from app.models import Notification

def handler(db,job):
    marker=os.getenv("SLOW_MARKER")
    if marker:
        job.lease_until=utcnow()+timedelta(seconds=.2)
    db.commit() # no database transaction remains during provider-equivalent I/O
    assert not db.in_transaction()
    if marker:Path(marker).touch()
    time.sleep(1.2 if marker else .03)
    jobs.assert_lease(db,job)
    db.add(Notification(id=job.id,learner_id=job.learner_id,kind="worker-test",title="Synthetic exactly-once effect"))
    return {"worker":"slow" if marker else "fast"}
jobs.register("synthetic-worker",handler)
for _ in range(20 if not os.getenv("SLOW_MARKER") else 1):
    if not jobs.run_once():time.sleep(.015)
'''

def spawn(environment):
    return subprocess.Popen([str(BACKEND/".venv/bin/python"),"-c",PROGRAM],cwd=BACKEND,env=environment,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)

def check(process):
    output,error=process.communicate(timeout=20)
    assert process.returncode==0,error


def test_two_workers_claim_once_after_checkpoint(pg):
    environment,factory,uid=pg
    with factory() as db:
        db.add_all([Job(learner_id=uid,kind="synthetic-worker") for _ in range(8)]);db.commit()
    workers=[spawn(environment),spawn(environment)]
    for worker in workers:check(worker)
    with factory() as db:
        rows=list(db.scalars(select(Job)))
        assert len(rows)==8 and all(j.state=="succeeded" and j.attempts==1 for j in rows)
        assert len(list(db.scalars(select(Notification))))==8
        assert len({j.lease_owner for j in rows})==1 and rows[0].lease_owner is None


def test_expired_provider_checkpoint_cannot_apply_stale_output(pg,tmp_path):
    environment,factory,uid=pg
    with factory() as db:
        job=Job(learner_id=uid,kind="synthetic-worker");db.add(job);db.commit();jid=job.id
    marker=tmp_path/"slow-provider-started"
    slow=spawn({**environment,"SLOW_MARKER":str(marker)})
    deadline=time.monotonic()+5
    while not marker.exists() and time.monotonic()<deadline:time.sleep(.02)
    assert marker.exists()
    time.sleep(.3) # controlled expiry while slow provider-equivalent I/O is pending
    fast=spawn(environment)
    check(fast);check(slow)
    with factory() as db:
        job=db.get(Job,jid)
        assert job.state=="succeeded" and job.result=={"worker":"fast"} and job.attempts==2
        assert len(list(db.scalars(select(Notification))))==1
