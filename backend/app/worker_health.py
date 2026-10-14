"""Container-local durable-worker health; another worker cannot mask failure."""
import socket

from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError

from .db import SessionLocal, as_utc, utcnow
from .models import WorkerHeartbeat
from .settings import settings


def is_ready(db, hostname=None, now=None):
    prefix = (hostname or socket.gethostname()) + ":"
    checked = db.scalar(
        select(func.max(WorkerHeartbeat.checked_at)).where(
            WorkerHeartbeat.worker_id.startswith(prefix, autoescape=True)
        )
    )
    if not checked:
        return False
    age = ((now or utcnow()) - as_utc(checked)).total_seconds()
    return 0 <= age < settings.worker_freshness_seconds


def main():
    try:
        with SessionLocal() as db:
            return 0 if is_ready(db) else 1
    except (SQLAlchemyError, OSError):
        # Health output must not contain database URLs or connection secrets.
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
