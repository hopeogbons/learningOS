"""Sleeping maintenance cannot consume learner intake/rate budgets forever."""
from datetime import timedelta, timezone

import pytest
from sqlalchemy import create_engine, select, func
from sqlalchemy.orm import Session

from app.db import Base, utcnow
from app.models import Collection, Job, Learner
from app.jobs import enqueue, JobBudgetExceeded, MAX_SCHEDULED_DRIVE_POLLS
from app.settings import settings


@pytest.fixture
def db(monkeypatch):
    monkeypatch.setattr(settings, 'app_mode', 'connected')
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as session:
        session.add(Learner(id='synthetic-owner'))
        session.commit()
        yield session
    engine.dispose()


def test_twenty_five_sleeping_polls_allow_actual_interactive_intake(db, monkeypatch, tmp_path):
    from app.ingestion_api import create_intake
    from app.storage import LocalStorage
    monkeypatch.setattr('app.ingestion_api.get_storage', lambda: LocalStorage(tmp_path))
    learner = db.get(Learner, 'synthetic-owner')
    collection = Collection(learner_id=learner.id, name='My own notes', storage_mode='local')
    db.add(collection); db.commit()
    for index in range(25):
        enqueue(db, learner.id, 'drive-sync', {'collection_id': f'collection-{index}'},
                f'poll:collection-{index}:previous', run_at=utcnow() + timedelta(minutes=1))
    db.commit()
    intake = create_intake(db, learner, collection, 'own-notes.txt', 'txt', b'My original notes.', 'text/plain', 'upload-one')
    assert intake['status'] == 'queued'
    assert db.get(Job, intake['job_id']).state == 'queued'
    assert db.scalar(select(func.count(Job.id))) == 26


@pytest.mark.parametrize('kind,key,state,scheduled', [
    ('drive-sync', 'poll:collection:', 'queued', -1),
    ('drive-sync', 'initial-poll:collection:', 'queued', -1),
    ('drive-sync', 'poll:collection:', 'running', 1),
    ('drive-sync', 'manual-sync:collection:', 'queued', 1),
    ('session.generate', 'poll:collection:', 'queued', 1),
])
def test_due_running_manual_and_non_drive_jobs_still_bound_runnable_work(db, kind, key, state, scheduled):
    for index in range(20):
        db.add(Job(learner_id='synthetic-owner', kind=kind, idempotency_key=key + str(index), payload={}, state=state, run_at=utcnow() + timedelta(minutes=scheduled)))
    db.commit()
    with pytest.raises(JobBudgetExceeded):
        enqueue(db, 'synthetic-owner', 'session.generate', {'session_id': 'synthetic-session'}, 'interactive')
    # A future poll can be scheduled without admitting more runnable work.
    future = enqueue(db, 'synthetic-owner', 'drive-sync', {'collection_id': 'new-collection'},
                     'poll:new-collection:previous', run_at=utcnow() + timedelta(minutes=1))
    assert future.run_at > utcnow()


def test_maintenance_does_not_spend_interactive_rate_budget_but_manual_sync_does(db):
    for index in range(60):
        db.add(Job(learner_id='synthetic-owner', kind='drive-sync', idempotency_key=f'poll:collection:{index}', payload={}, state='succeeded'))
    db.commit()
    first = enqueue(db, 'synthetic-owner', 'session.generate', {'session_id': 'synthetic-session'}, 'first')
    first.state = 'succeeded'
    for index in range(49):
        db.add(Job(learner_id='synthetic-owner', kind='drive-sync', idempotency_key=f'manual-sync:collection:{index}', payload={}, state='succeeded'))
    db.commit()
    with pytest.raises(JobBudgetExceeded):
        enqueue(db, 'synthetic-owner', 'session.generate', {'session_id': 'synthetic-session'}, 'rate-overflow')
    assert enqueue(db, 'synthetic-owner', 'session.generate', {'session_id': 'synthetic-session'}, 'first').id == first.id


def test_delayed_automatic_queue_has_its_own_finite_capacity(db):
    for index in range(MAX_SCHEDULED_DRIVE_POLLS):
        db.add(Job(learner_id='synthetic-owner', kind='drive-sync', idempotency_key=f'poll:collection-{index}:previous', payload={}, state='queued', run_at=utcnow() + timedelta(minutes=1)))
    db.commit()
    with pytest.raises(JobBudgetExceeded):
        enqueue(db, 'synthetic-owner', 'drive-sync', {'collection_id': 'overflow'},
                'poll:overflow:previous', run_at=utcnow() + timedelta(minutes=1))
    assert enqueue(db, 'synthetic-owner', 'session.generate', {'session_id': 'synthetic-session'}, 'still-interactive').state == 'queued'


def test_enqueue_normalizes_schedule_before_sqlite_drops_timezone(db):
    expected = utcnow() + timedelta(minutes=1)
    supplied = expected.astimezone(timezone(timedelta(hours=5, minutes=30)))
    job = enqueue(db, 'synthetic-owner', 'drive-sync', {'collection_id': 'timezone-collection'}, 'poll:timezone-collection:previous', run_at=supplied)
    assert job.run_at == expected and job.run_at.utcoffset() == timedelta(0)
    db.commit(); db.refresh(job)
    assert job.run_at.replace(tzinfo=timezone.utc) == expected
