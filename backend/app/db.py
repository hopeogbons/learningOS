from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from .settings import settings

class Base(DeclarativeBase):
    pass

def utcnow():
    return datetime.now(timezone.utc)

def as_utc(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value

if settings.database_url.startswith("sqlite:///"):
    Path(settings.database_url[10:]).parent.mkdir(parents=True, exist_ok=True)
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args={"check_same_thread": False} if settings.database_url.startswith("sqlite") else {})
if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def sqlite_pragmas(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as db:
        try:
            yield db
        except Exception:
            db.rollback()
            raise
