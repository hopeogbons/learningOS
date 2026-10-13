"""Idempotent synthetic demo seed; never runs in connected/production mode."""
import hashlib
from pathlib import Path
from sqlalchemy import select
from .settings import settings
from .db import SessionLocal
from .auth import DEMO_LEARNER_ID
from .models import Learner, Collection, Material, MaterialRevision, Chunk, ScopeRevision, ScopeItem

def seed_demo():
    if settings.app_mode not in {"demo", "test"}:
        raise RuntimeError("Demo fixtures are forbidden in live/production mode")
    from .sources.local import extract_file
    from .ingest import persist_snapshot
    from .storage import get_storage
    fixture_root = Path(__file__).resolve().parents[2] / "fixtures"
    with SessionLocal() as db:
        learner = db.get(Learner, DEMO_LEARNER_ID)
        if not learner:
            learner = Learner(id=DEMO_LEARNER_ID, display_name="Demo Learner", is_demo=True, speech_locale="en-GB")
            db.add(learner)
            db.flush()
        collection = db.scalar(select(Collection).where(Collection.learner_id == learner.id, Collection.name == "Chemistry • Sample material"))
        if not collection:
            collection = Collection(learner_id=learner.id, name="Chemistry • Sample material", note="Synthetic licensed demo fixtures; no live AI or Drive", icon_key="flask", color_key="blue", storage_mode="local", provisioning_state="local-only", position=0)
            db.add(collection)
            db.flush()
        for index, filename in enumerate(("chem_ch3.md", "chem_ch4.md")):
            data = (fixture_root / filename).read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            existing = db.scalar(select(MaterialRevision).where(MaterialRevision.learner_id == learner.id, MaterialRevision.collection_id == collection.id, MaterialRevision.content_hash == digest))
            if existing:
                continue
            material = Material(learner_id=learner.id, collection_id=collection.id, title="Chapter 3 — Atoms" if index == 0 else "Chapter 4 — Bonds", source_type="markdown", position=index)
            db.add(material)
            db.flush()
            revision = MaterialRevision(learner_id=learner.id, collection_id=collection.id, material_id=material.id, content_hash=digest, origin="ui_upload", storage_state="local-only", private_blob_key=get_storage().put(learner.id, data, filename), mime="text/markdown", size=len(data), source_language="en", metadata_json={"demo_fixture": True, "synthetic": True})
            db.add(revision)
            db.flush()
            persist_snapshot(db, revision, extract_file(data, filename, "text/markdown"))
            revision.source_language = "en"
        scope = db.scalar(select(ScopeRevision).where(ScopeRevision.learner_id == learner.id, ScopeRevision.collection_id == collection.id, ScopeRevision.active.is_(True)))
        if not scope:
            chunks = db.scalars(select(Chunk).join(MaterialRevision, MaterialRevision.id == Chunk.material_revision_id).join(Material, Material.id == MaterialRevision.material_id).where(Chunk.learner_id == learner.id, Material.collection_id == collection.id).order_by(Material.position, Chunk.position)).all()
            selected = [c for c in chunks if c.title in {"Atomic number", "Isotopes", "Electron shells", "Ionic bonding", "Covalent bonding"}]
            scope = ScopeRevision(learner_id=learner.id, collection_id=collection.id, revision_number=1)
            db.add(scope)
            db.flush()
            for index, chunk in enumerate(selected):
                db.add(ScopeItem(learner_id=learner.id, scope_revision_id=scope.id, chunk_id=chunk.id, position=index))
        db.commit()
        return {"learner_id": learner.id, "collection_id": collection.id, "scope_revision_id": scope.id}

if __name__ == "__main__":
    import json
    print(json.dumps(seed_demo()))
