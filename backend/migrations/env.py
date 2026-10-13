from alembic import context
from sqlalchemy import create_engine, pool
from app.db import Base
from app import models
from app.settings import settings

config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))
target_metadata = Base.metadata

def run_migrations_offline():
    context.configure(url=settings.database_url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"}, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online():
    from app.db import engine
    with engine.connect() as connection:
        sqlite = connection.dialect.name == "sqlite"
        # SQLite batch table rebuilds need FK enforcement suspended during controlled
        # schema migration; validate references and restore enforcement afterwards.
        if sqlite:
            connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
            connection.commit()
        try:
            context.configure(connection=connection, target_metadata=target_metadata, compare_type=True, render_as_batch=sqlite)
            with context.begin_transaction():
                context.run_migrations()
            if sqlite:
                violations = connection.exec_driver_sql("PRAGMA foreign_key_check").all()
                if violations:
                    raise RuntimeError("Migration foreign-key validation failed")
        finally:
            if sqlite:
                connection.commit()
                connection.exec_driver_sql("PRAGMA foreign_keys=ON")
                connection.commit()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
