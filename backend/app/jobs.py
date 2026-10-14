"""DB queue with atomic leases, transaction-owned handlers and durable outbox."""
import os
import socket
from datetime import timedelta, timezone
from sqlalchemy import select, update, or_, and_
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException
from .settings import settings
from .db import SessionLocal, utcnow, as_utc
from .models import Job, OutboxEvent, WorkerHeartbeat, Notification, Learner

HANDLERS = {}
WORKER_ID = f"{socket.gethostname()}:{os.getpid()}"
MAX_ATTEMPTS = 4
MAX_SCHEDULED_DRIVE_POLLS = 1000

class NeedsAttention(Exception):
    def __init__(self, code="needs_attention"):
        self.code = code
        super().__init__(code)

class RetryableJobError(Exception):
    def __init__(self, code="provider_unavailable"):
        self.code = code
        super().__init__(code)

def register(kind, handler=None):
    def install(fn):
        HANDLERS[kind] = fn
        return fn
    return install(handler) if handler is not None else install

class JobBudgetExceeded(HTTPException):
    code = "job_budget_exceeded"
    def __init__(self):
        super().__init__(429, self.code, headers={"Retry-After": "60"})

def automatic_drive_poll():
    """Only internal polling keys identify maintenance; manual Sync stays interactive."""
    from sqlalchemy import func
    key = func.coalesce(Job.idempotency_key, "")
    return and_(Job.kind == "drive-sync", or_(key.startswith("poll:"), key.startswith("initial-poll:")))


def check_job_budget(db, learner_id, delayed_poll=False):
    """A tenant row lock serializes admission across PostgreSQL API/worker hosts."""
    if settings.app_mode not in {"live", "connected", "production"}:
        return
    # This short write serializes admission on SQLite as well as PostgreSQL.
    db.execute(update(Learner).where(Learner.id == learner_id).values(id=Learner.id))
    from sqlalchemy import func
    now = utcnow()
    automatic = automatic_drive_poll()
    if delayed_poll:
        scheduled = db.scalar(select(func.count()).select_from(Job).where(Job.learner_id == learner_id, automatic, Job.state.in_(["queued", "running"])))
        if scheduled >= MAX_SCHEDULED_DRIVE_POLLS:
            raise JobBudgetExceeded()
        return
    sleeping_poll = and_(automatic, Job.state == "queued", Job.run_at > now)
    outstanding = db.scalar(select(func.count()).select_from(Job).where(Job.learner_id == learner_id, Job.state.in_(["queued", "running"]), ~sleeping_poll))
    recent = db.scalar(select(func.count()).select_from(Job).where(Job.learner_id == learner_id, Job.created_at >= now - timedelta(minutes=1), ~automatic))
    if outstanding >= 20 or recent >= 50:
        raise JobBudgetExceeded()

def enqueue(db, learner_id, kind, payload, idempotency_key=None, run_at=None):
    if run_at is not None:
        run_at = as_utc(run_at).astimezone(timezone.utc)
    if idempotency_key:
        existing = db.scalar(select(Job).where(Job.learner_id == learner_id, Job.idempotency_key == idempotency_key))
        if existing:
            return existing
    if kind != "delete-learner":
        delayed_poll = (kind == "drive-sync" and bool(payload.get("collection_id"))
                        and bool(idempotency_key and idempotency_key.startswith("poll:"))
                        and run_at is not None and run_at > utcnow())
        check_job_budget(db, learner_id, delayed_poll=delayed_poll)
    job = Job(learner_id=learner_id, kind=kind, payload=payload, idempotency_key=idempotency_key, entity_id=payload.get("entity_id") or payload.get("material_id") or payload.get("session_id") or payload.get("collection_id"))
    if run_at is not None:
        job.run_at = run_at
    try:
        with db.begin_nested():
            db.add(job)
            db.flush()
    except IntegrityError:
        if not idempotency_key:
            raise
        return db.scalar(select(Job).where(Job.learner_id == learner_id, Job.idempotency_key == idempotency_key))
    return job

def publish_outbox(db, learner_id, aggregate_id, aggregate_version, event_type, payload):
    event = db.scalar(select(OutboxEvent).where(OutboxEvent.aggregate_id == aggregate_id, OutboxEvent.aggregate_version == aggregate_version, OutboxEvent.event_type == event_type))
    if not event:
        event = OutboxEvent(learner_id=learner_id, aggregate_id=aggregate_id, aggregate_version=aggregate_version, event_type=event_type, payload=payload)
        db.add(event)
        db.flush()
    return event

def heartbeat(db):
    row = db.scalar(select(WorkerHeartbeat).where(WorkerHeartbeat.worker_id == WORKER_ID))
    if row:
        row.checked_at = utcnow()
    else:
        db.add(WorkerHeartbeat(worker_id=WORKER_ID))

def dispatch_outbox(db):
    events = db.scalars(select(OutboxEvent).where(OutboxEvent.processed_at.is_(None)).limit(100).with_for_update(skip_locked=True)).all()
    for event in events:
        enqueue(db, event.learner_id, event.event_type, event.payload, f"outbox:{event.id}")
        event.processed_at = utcnow()

class LostLease(Exception):
    pass

def assert_lease(db, job):
    # Read DB owner after checkpoint/network work, never trust stale ORM state.
    owner, until = db.execute(select(Job.lease_owner, Job.lease_until).where(Job.id == job.id).with_for_update()).one()
    if owner != WORKER_ID or not until or as_utc(until) <= utcnow():
        raise LostLease("lease_lost")

def run_once():
    now = utcnow()
    eligible = and_(Job.run_at <= now, or_(Job.state == "queued", and_(Job.state == "running", Job.lease_until < now)))
    with SessionLocal() as db:
        heartbeat(db)
        dispatch_outbox(db)
        db.execute(update(Job).where(Job.state == "running", Job.lease_until < now, Job.attempts >= MAX_ATTEMPTS).values(state="failed", error_code="lease_exhausted", retryable=True, lease_owner=None, lease_until=None).execution_options(synchronize_session=False))
        db.commit()
        query = select(Job).where(eligible).order_by(Job.run_at, Job.created_at).limit(1)
        if db.bind.dialect.name == "postgresql":
            query = query.with_for_update(skip_locked=True)
        candidate = db.scalar(query)
        if not candidate:
            return False
        candidate_id = candidate.id
        lease = now + timedelta(seconds=300)
        changed = db.execute(update(Job).where(Job.id == candidate_id, eligible).values(state="running", lease_owner=WORKER_ID, lease_until=lease, attempts=Job.attempts + 1, progress=1).execution_options(synchronize_session=False))
        db.commit()
        if changed.rowcount != 1:
            return False
    try:
        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.id == candidate_id, Job.lease_owner == WORKER_ID).with_for_update())
            if not job or as_utc(job.lease_until) <= utcnow():
                return False
            handler = HANDLERS.get(job.kind)
            if not handler:
                raise NeedsAttention("unsupported_job_kind")
            result = handler(db, job)
            # Providers may checkpoint before I/O. Final evidence requires valid lease.
            assert_lease(db, job)
            job.result = result or {}
            job.state = "succeeded"
            job.progress = 100
            job.error_code = None
            job.lease_owner = None
            job.lease_until = None
            db.commit()
    except LostLease:
        return True
    except Exception as exc:
        with SessionLocal() as db:
            job = db.scalar(select(Job).where(Job.id == candidate_id, Job.lease_owner == WORKER_ID))
            if job:
                attention = isinstance(exc, NeedsAttention) or not isinstance(exc, (RetryableJobError, JobBudgetExceeded))
                job.error_code = getattr(exc, "code", "job_failed")
                job.retryable = isinstance(exc, (RetryableJobError, JobBudgetExceeded))
                job.state = "needs-attention" if attention else "queued" if job.attempts < MAX_ATTEMPTS else "failed"
                job.run_at = utcnow() + timedelta(seconds=min(300, 2 ** job.attempts))
                job.lease_owner = None
                job.lease_until = None
                if job.state in {"failed", "needs-attention"}:
                    db.add(Notification(learner_id=job.learner_id, kind="job", title="Material needs attention", body=job.error_code, entity_id=job.id))
                db.commit()
    return True
