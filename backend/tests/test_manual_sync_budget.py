"""Manual Sync admits user work without creating parallel maintenance chains."""
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base, utcnow, as_utc
from app.models import Collection, Job, Learner, ProviderConnection
from app.jobs import enqueue, JobBudgetExceeded
from app.ingestion_api import sync
from app.settings import settings


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, 'app_mode', 'connected')
    engine=create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as session:
        learner=Learner(id='synthetic-owner')
        other=Learner(id='synthetic-other')
        session.add_all([learner,other]);session.flush()
        session.add(Collection(id='collection',learner_id=learner.id,name='My files',storage_mode='drive',provisioning_state='ready',drive_folder_id='synthetic-folder',drive_root_id='synthetic-root'))
        session.commit()
        yield session,learner
    engine.dispose()


def sleeping_poll(db):
    return enqueue(db,'synthetic-owner','drive-sync',{'collection_id':'collection'},'poll:collection:previous',run_at=utcnow()+timedelta(minutes=1))


def test_manual_sync_replaces_sleeping_poll_once_and_resumes_one_chain(db,monkeypatch):
    from app import ingest
    from app.sources.drive import SCOPES
    session,learner=db
    old=sleeping_poll(session);session.commit()
    result=sync('collection',session,learner)
    manual=session.get(Job,result['job_id'])
    assert manual.id!=old.id and manual.idempotency_key.startswith('manual-sync:collection:')
    assert old.state=='cancelled' and manual.state=='queued'
    assert sync('collection',session,learner)['job_id']==manual.id
    session.add(ProviderConnection(learner_id=learner.id,provider='drive',status='connected',encrypted_credentials='synthetic',scopes=SCOPES));session.commit()
    class Adapter:
        def get_file(self,*_):return {'id':'synthetic-folder','parents':['synthetic-root']}
        def list_files(self,*_):return []
    monkeypatch.setattr(ingest,'drive_adapter',lambda *_:Adapter())
    manual.state='running';session.commit()
    ingest.sync_drive(session,manual)
    manual.state='succeeded';session.commit()
    active=session.scalars(select(Job).where(Job.kind=='drive-sync',Job.state.in_(['queued','running']))).all()
    assert len(active)==1 and active[0].idempotency_key.startswith('poll:collection:')
    assert as_utc(active[0].run_at)>utcnow()


@pytest.mark.parametrize('budget',['runnable','recent'])
def test_rejected_manual_admission_preserves_original_sleeping_poll(db,budget):
    session,learner=db
    old=sleeping_poll(session)
    count=20 if budget=='runnable' else 50
    for index in range(count):
        session.add(Job(learner_id=learner.id,kind='session.generate',idempotency_key=f'other-work:{index}',payload={},state='queued' if budget=='runnable' else 'succeeded'))
    session.commit();old_run_at=old.run_at
    with pytest.raises(JobBudgetExceeded):sync('collection',session,learner)
    session.rollback();session.refresh(old)
    assert old.state=='queued' and old.run_at.replace(tzinfo=old_run_at.tzinfo)==old_run_at
    assert not session.scalar(select(Job).where(Job.idempotency_key.startswith('manual-sync:')))


@pytest.mark.parametrize('state',['queued','running'])
def test_due_or_running_work_is_reused_even_when_budget_full(db,state):
    session,learner=db
    existing=Job(learner_id=learner.id,kind='drive-sync',entity_id='collection',idempotency_key='poll:collection:due',payload={'collection_id':'collection'},state=state,run_at=utcnow()-timedelta(seconds=1))
    session.add(existing)
    for index in range(20):session.add(Job(learner_id=learner.id,kind='session.generate',payload={},state='queued'))
    session.commit()
    assert sync('collection',session,learner)['job_id']==existing.id
    assert existing.state==state


def test_other_learner_cannot_cancel_or_promote_owner_poll(db):
    session,learner=db
    old=sleeping_poll(session);session.commit()
    with pytest.raises(HTTPException) as caught:sync('collection',session,session.get(Learner,'synthetic-other'))
    assert caught.value.status_code==404 and old.state=='queued'
