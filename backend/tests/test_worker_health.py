"""Worker health must use its own container, including after failed startup."""
from datetime import timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.db import Base, utcnow
from app.models import WorkerHeartbeat
from app import worker_health


@pytest.mark.parametrize("own_age, other_host, expected", [
    (1, "other", True),
    (120, "other", False),
    (180, "other", False),
    (None, "other", False),
    (-30, "other", False),
    (None, "workerXone", False),
])
def test_own_container_freshness_cannot_be_masked(own_age, other_host, expected):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    now = utcnow()
    with Session(engine) as db:
        db.add(WorkerHeartbeat(worker_id=other_host + ":1", checked_at=now))
        if own_age is not None:
            db.add(WorkerHeartbeat(worker_id="worker_one:1", checked_at=now - timedelta(seconds=own_age)))
        db.commit()
        assert worker_health.is_ready(db, hostname="worker_one", now=now) is expected
    engine.dispose()


def test_database_failure_returns_unhealthy_without_secret_output(monkeypatch, capsys):
    def unavailable():
        raise SQLAlchemyError("synthetic-private-connection-details")
    monkeypatch.setattr(worker_health, "SessionLocal", unavailable)
    assert worker_health.main() == 1
    assert capsys.readouterr() == ("", "")
