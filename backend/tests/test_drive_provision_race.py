"""Collections admitted during provision must not be stranded on a finished job."""
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db import Base
from app.models import Collection, Job, Learner, ProviderConnection
from app import ingest
from app.sources.drive import SCOPES


def test_running_provision_includes_collection_created_during_provider_call(monkeypatch):
    engine = create_engine('sqlite://')
    Base.metadata.create_all(engine)
    with sessionmaker(engine, expire_on_commit=False)() as db:
        learner = Learner(display_name='Synthetic', is_demo=False)
        db.add(learner); db.flush()
        db.add(ProviderConnection(learner_id=learner.id, provider='drive', status='connected', encrypted_credentials='synthetic', scopes=SCOPES))
        first = Collection(learner_id=learner.id, name='First', storage_mode='drive', provisioning_state='pending')
        db.add(first); db.flush()
        job = ingest.queue_provision(db, learner.id, first.id)
        job.state = 'running'; db.commit()
        calls = []

        class Adapter:
            def ensure_folder(self, identity, name, parent=None, existing_id=None):
                calls.append(identity)
                if identity == f'collection:{first.id}':
                    second = Collection(learner_id=learner.id, name='Second', storage_mode='drive', provisioning_state='pending')
                    db.add(second); db.flush()
                    assert ingest.queue_provision(db, learner.id, second.id).id == job.id
                    db.commit()
                return {'id': f'synthetic-{identity}'}

        monkeypatch.setattr(ingest, 'drive_adapter', lambda *_: Adapter())
        result = ingest.provision_drive(db, job)
        job.state = 'succeeded'; db.commit()
        collections = db.scalars(select(Collection).order_by(Collection.name)).all()
        assert result['collection_count'] == 2
        assert len(calls) == 3  # one root and both distinct Collection identities
        assert all(c.provisioning_state == 'ready' for c in collections)
        assert len({c.drive_folder_id for c in collections}) == 2
        assert db.scalars(select(Job).where(Job.kind == 'drive-provision')).all() == [job]
        assert len(db.scalars(select(Job).where(Job.kind == 'drive-sync', Job.state == 'queued')).all()) == 2
        # A request after completion reuses/requeues the durable provision job.
        third = Collection(learner_id=learner.id, name='Third', storage_mode='drive', provisioning_state='pending')
        db.add(third); db.flush()
        assert ingest.queue_provision(db, learner.id, third.id).id == job.id
        assert job.state == 'queued'
    engine.dispose()
