"""Authenticated core routes: immutable scopes, ordering, progress and private data."""
import hashlib
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, ConfigDict
from sqlalchemy import select, func, update, delete, or_, literal, union_all
from .db import get_db, utcnow, as_utc
from .models import *
from .auth import get_learner
from .settings import settings
from .jobs import enqueue, register, NeedsAttention

from .core_schemas import *

router = APIRouter()
import json
from pathlib import Path
LANGUAGE_REGISTRY = json.loads((Path(__file__).resolve().parents[2] / "contracts/language-registry.json").read_text())["languages"]
LOCALES = [(v["ui_locale"], v["native_label"], v["english_label"], v["direction"]) for v in LANGUAGE_REGISTRY]
SPEECH_LOCALES = {v["default_speech_locale"] for v in LANGUAGE_REGISTRY}

def owned(db, cls, entity_id, learner_id):
    row = db.scalar(select(cls).where(cls.id == entity_id, cls.learner_id == learner_id))
    if row is None:
        raise HTTPException(404, "not_found")
    return row

def iso(value):
    return as_utc(value).isoformat() if value else None

def learner_dto(row):
    return {"id": row.id, "display_name": row.display_name, "ui_locale": row.ui_locale, "study_locale": row.study_locale, "speech_locale": row.speech_locale, "timezone": row.timezone, "is_demo": row.is_demo, "mode": settings.app_mode}

def active_scope(db, collection_id, learner_id):
    return db.scalar(select(ScopeRevision).where(ScopeRevision.collection_id == collection_id, ScopeRevision.learner_id == learner_id, ScopeRevision.active.is_(True)))

def scope_dto(db, scope):
    if not scope:
        return None
    return {"id": scope.id, "revision_number": scope.revision_number, "created_at": iso(scope.created_at), "chunk_ids": list(db.scalars(select(ScopeItem.chunk_id).where(ScopeItem.scope_revision_id == scope.id, ScopeItem.learner_id == scope.learner_id).order_by(ScopeItem.position)))}

def progress_dto(db, collection, scope=None):
    scope = scope or active_scope(db, collection.id, collection.learner_id)
    if not scope:
        return {"scope_revision_id": None, "completed_count": 0, "total_in_scope": 0, "percent": 0, "review_needed_count": 0}
    ids = list(db.scalars(select(ScopeItem.chunk_id).where(ScopeItem.scope_revision_id == scope.id, ScopeItem.learner_id == collection.learner_id)))
    completed = set(db.scalars(select(TitleAssessment.chunk_id).where(TitleAssessment.learner_id == collection.learner_id, TitleAssessment.scope_revision_id == scope.id, TitleAssessment.complete.is_(True), TitleAssessment.chunk_id.in_(ids)))) if ids else set()
    needed = db.scalar(select(func.count()).select_from(ReviewState).where(ReviewState.learner_id == collection.learner_id, ReviewState.chunk_id.in_(ids), or_(ReviewState.needs_attention.is_(True), ReviewState.next_review_at <= utcnow()))) if ids else 0
    return {"scope_revision_id": scope.id, "completed_count": len(completed), "total_in_scope": len(ids), "percent": round(100 * len(completed) / len(ids)) if ids else 0, "review_needed_count": needed}

def collection_dtos(db, rows):
    """Bounded query count regardless of collection count in the dashboard snapshot."""
    if not rows:
        return []
    learner_id = rows[0].learner_id
    collection_ids = [row.id for row in rows]
    scopes = list(db.scalars(select(ScopeRevision).where(ScopeRevision.learner_id == learner_id, ScopeRevision.collection_id.in_(collection_ids), ScopeRevision.active.is_(True))))
    scopes_by_collection = {row.collection_id: row for row in scopes}
    scope_ids = [row.id for row in scopes]
    scope_items = list(db.scalars(select(ScopeItem).where(ScopeItem.learner_id == learner_id, ScopeItem.scope_revision_id.in_(scope_ids)).order_by(ScopeItem.position))) if scope_ids else []
    chunks_by_scope = {}
    for item in scope_items:
        chunks_by_scope.setdefault(item.scope_revision_id, []).append(item.chunk_id)
    completed = set(db.execute(select(TitleAssessment.scope_revision_id, TitleAssessment.chunk_id).where(TitleAssessment.learner_id == learner_id, TitleAssessment.scope_revision_id.in_(scope_ids), TitleAssessment.complete.is_(True))).all()) if scope_ids else set()
    chunk_ids = {item.chunk_id for item in scope_items}
    needed = set(db.scalars(select(ReviewState.chunk_id).where(ReviewState.learner_id == learner_id, ReviewState.chunk_id.in_(chunk_ids), or_(ReviewState.needs_attention.is_(True), ReviewState.next_review_at <= utcnow())))) if chunk_ids else set()
    material_counts = dict(db.execute(select(Material.collection_id, func.count()).where(Material.learner_id == learner_id, Material.collection_id.in_(collection_ids), Material.archived.is_(False)).group_by(Material.collection_id)).all())
    result = []
    for row in rows:
        scope = scopes_by_collection.get(row.id)
        selected = chunks_by_scope.get(scope.id, []) if scope else []
        done = sum((scope.id, cid) in completed for cid in selected) if scope else 0
        progress = {"scope_revision_id": scope.id if scope else None, "completed_count": done, "total_in_scope": len(selected), "percent": round(100 * done / len(selected)) if selected else 0, "review_needed_count": len(set(selected) & needed)}
        result.append({"id": row.id, "name": row.name, "note": row.note, "icon_key": row.icon_key, "color_key": row.color_key, "storage_mode": row.storage_mode, "folder_mode": row.folder_mode, "provisioning_state": row.provisioning_state, "drive_folder_id": row.drive_folder_id, "position": row.position, "version": row.version, "archived": row.archived, "created_at": iso(row.created_at), "last_sync": iso(row.last_sync), "last_sync_at": iso(row.last_sync), "material_count": material_counts.get(row.id, 0), "active_scope": {"id": scope.id, "revision_number": scope.revision_number, "created_at": iso(scope.created_at), "chunk_ids": selected} if scope else None, "progress": progress})
    return result

def collection_dto(db, row):
    return collection_dtos(db, [row])[0]

def material_dto(db, row, revision_cache=None):
    revision = revision_cache.get(row.current_revision_id) if revision_cache is not None else db.scalar(select(MaterialRevision).where(MaterialRevision.id == row.current_revision_id, MaterialRevision.learner_id == row.learner_id)) if row.current_revision_id else None
    return {"id": row.id, "collection_id": row.collection_id, "title": row.title, "source_type": row.source_type, "position": row.position, "version": row.version, "status": row.status, "current_revision_id": row.current_revision_id, "created_at": iso(row.created_at), "origin": revision.origin if revision else None, "source_language": revision.source_language if revision else "und", "storage_state": revision.storage_state if revision else "pending", "size": revision.size if revision else 0, "deletion_job_id": row.deletion_job_id}

def material_cache(db, rows):
    if not rows:
        return {}
    return {revision.id: revision for revision in db.scalars(select(MaterialRevision).where(MaterialRevision.learner_id == rows[0].learner_id, MaterialRevision.id.in_([row.current_revision_id for row in rows if row.current_revision_id])))}

def material_dtos(db, rows):
    cache = material_cache(db, rows)
    return [material_dto(db, row, cache) for row in rows]

def version_claim(db, cls, row, expected_version):
    changed = db.execute(update(cls).where(cls.id == row.id, cls.learner_id == row.learner_id, cls.version == expected_version).values(version=expected_version + 1).execution_options(synchronize_session=False))
    if changed.rowcount != 1:
        raise HTTPException(409, "version_conflict")
    db.refresh(row)

class ProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(None, min_length=1, max_length=120)
    ui_locale: str | None = None
    study_locale: str | None = None
    speech_locale: str | None = None
    timezone: str | None = None

@router.get("/me", response_model=LearnerDTO)
def me(learner=Depends(get_learner)):
    return learner_dto(learner)

@router.patch("/me", response_model=LearnerDTO)
def patch_me(body: ProfilePatch, learner=Depends(get_learner), db=Depends(get_db)):
    values = body.model_dump(exclude_none=True)
    for key, val in values.items():
        if key in {"ui_locale", "study_locale"} and val not in {item[0] for item in LOCALES}:
            raise HTTPException(422, "unsupported_locale")
        if key == "speech_locale" and val not in SPEECH_LOCALES:
            raise HTTPException(422, "unsupported_speech_locale")
        if key == "timezone":
            try:
                ZoneInfo(val)
            except (ZoneInfoNotFoundError, ValueError):
                raise HTTPException(422, "invalid_timezone") from None
        setattr(learner, key, val)
    db.commit()
    return learner_dto(learner)

@router.get("/languages", response_model=LanguageListDTO)
def languages():
    return {"items": [{"locale": code, "native_label": native, "english_label": english, "direction": direction, "ui": {"status": "catalog-candidate"}, "study": {"status": "unverified"}, "stt": {"status": "unverified"}, "tts": {"status": "unverified"}, "speech_variants": [v["default_speech_locale"] for v in LANGUAGE_REGISTRY if v["ui_locale"] == code]} for code, native, english, direction in LOCALES]}

class CollectionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=200)
    note: str = Field("", max_length=5000)
    icon_key: str = Field("book", max_length=50)
    color_key: str = Field("blue", max_length=50)
    storage_mode: Literal["local", "drive"] | None = None

class CollectionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    name: str | None = Field(None, min_length=1, max_length=200)
    note: str | None = Field(None, max_length=5000)
    icon_key: str | None = Field(None, max_length=50)
    color_key: str | None = Field(None, max_length=50)

@router.get("/collections", response_model=CollectionListDTO)
def collections(cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), learner=Depends(get_learner), db=Depends(get_db)):
    query = select(Collection).where(Collection.learner_id == learner.id, Collection.archived.is_(False))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Collection.position, Collection.id).offset(cursor).limit(limit)).all()
    return {"items": collection_dtos(db, rows), "total": total, "next_cursor": cursor + len(rows) if cursor + len(rows) < total else None}

@router.post("/collections", status_code=201, response_model=CollectionDTO)
def create_collection(body: CollectionCreate, learner=Depends(get_learner), db=Depends(get_db)):
    connection = db.scalar(select(ProviderConnection).where(ProviderConnection.learner_id == learner.id, ProviderConnection.provider == "drive", ProviderConnection.status == "connected"))
    mode = body.storage_mode or ("drive" if connection else "local")
    if mode == "drive" and not connection:
        raise HTTPException(409, "drive_not_connected")
    last_position = db.scalar(select(func.max(Collection.position)).where(Collection.learner_id == learner.id))
    position = (last_position if last_position is not None else -1) + 1
    row = Collection(learner_id=learner.id, **body.model_dump(exclude={"storage_mode"}), position=position, storage_mode=mode, provisioning_state="pending" if mode == "drive" else "local-only")
    db.add(row)
    db.flush()
    if mode == "drive":
        from .ingest import queue_provision
        job = queue_provision(db, learner.id, row.id)
        row.provisioning_job_id = job.id
    db.commit()
    return collection_dto(db, row)

@router.get("/collections/{collection_id}", response_model=CollectionDTO)
def get_collection(collection_id: str, learner=Depends(get_learner), db=Depends(get_db)):
    return collection_dto(db, owned(db, Collection, collection_id, learner.id))

@router.patch("/collections/{collection_id}", response_model=CollectionDTO)
def patch_collection(collection_id: str, body: CollectionPatch, learner=Depends(get_learner), db=Depends(get_db)):
    row = owned(db, Collection, collection_id, learner.id)
    version_claim(db, Collection, row, body.expected_version)
    for key, value in body.model_dump(exclude_none=True, exclude={"expected_version"}).items():
        setattr(row, key, value)
    db.commit()
    return collection_dto(db, row)

@router.delete("/collections/{collection_id}", response_model=ArchiveResultDTO)
def archive_collection(collection_id: str, expected_version: int, learner=Depends(get_learner), db=Depends(get_db)):
    row = owned(db, Collection, collection_id, learner.id)
    version_claim(db, Collection, row, expected_version)
    row.archived = True
    db.commit()
    return {"id": row.id, "state": "archived", "version": row.version}

@router.get("/collections/{collection_id}/materials", response_model=MaterialListDTO)
def materials(collection_id: str, cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), learner=Depends(get_learner), db=Depends(get_db)):
    owned(db, Collection, collection_id, learner.id)
    query = select(Material).where(Material.learner_id == learner.id, Material.collection_id == collection_id, Material.archived.is_(False))
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Material.position, Material.id).offset(cursor).limit(limit)).all()
    return {"items": material_dtos(db, rows), "total": total, "next_cursor": cursor + len(rows) if cursor + len(rows) < total else None}

class DeleteMaterialBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    confirmation: Literal["DELETE"]

@router.delete("/collections/{collection_id}/materials/{material_id}", status_code=202, response_model=JobDTO)
def delete_material(collection_id: str, material_id: str, body: DeleteMaterialBody,
                    learner=Depends(get_learner), db=Depends(get_db)):
    collection = owned(db, Collection, collection_id, learner.id)
    material = owned(db, Material, material_id, learner.id)
    if material.collection_id != collection.id:
        raise HTTPException(404, "not_found")
    key = f"delete-material:{material.id}"
    existing = db.scalar(select(Job).where(Job.learner_id == learner.id, Job.idempotency_key == key))
    if existing and existing.state in {"queued", "running"}:
        material.deletion_job_id = existing.id
        db.commit()
        return job_dto(existing)

    version_claim(db, Material, material, body.expected_version)
    material.status = "deleting"
    if existing:
        existing.state = "queued"
        existing.run_at = utcnow()
        existing.attempts = 0
        existing.progress = 0
        existing.error_code = None
        existing.retryable = True
        existing.lease_owner = None
        existing.lease_until = None
        existing.result = {}
    else:
        existing = enqueue(
            db,
            learner.id,
            "delete-material",
            {"material_id": material.id, "collection_id": collection.id},
            idempotency_key=key,
        )
    material.deletion_job_id = existing.id
    db.commit()
    return job_dto(existing)

@router.get("/collections/{collection_id}/outline", response_model=OutlineDTO)
def outline(collection_id: str, learner=Depends(get_learner), db=Depends(get_db)):
    collection = owned(db, Collection, collection_id, learner.id)
    scope = active_scope(db, collection.id, learner.id)
    selected = set(db.scalars(select(ScopeItem.chunk_id).where(ScopeItem.scope_revision_id == scope.id, ScopeItem.learner_id == learner.id))) if scope else set()
    material_rows = db.scalars(select(Material).where(Material.collection_id == collection_id, Material.learner_id == learner.id, Material.archived.is_(False)).order_by(Material.position, Material.id)).all()
    revisions = [row.current_revision_id for row in material_rows if row.current_revision_id]
    chunks = db.scalars(select(Chunk).where(Chunk.learner_id == learner.id, Chunk.material_revision_id.in_(revisions)).order_by(Chunk.position, Chunk.id)).all() if revisions else []
    concepts = db.execute(select(Concept.chunk_id, Concept.citation_ids).where(Concept.learner_id == learner.id, Concept.chunk_id.in_([c.id for c in chunks]))).all() if chunks else []
    citations = {}
    for chunk_id, citation_ids in concepts:
        citations.setdefault(chunk_id, set()).update(citation_ids)
    result = []
    cache = material_cache(db, material_rows)
    for material in material_rows:
        data = material_dto(db, material, cache)
        data["chunks"] = [{"id": c.id, "title": c.title, "position": c.position, "citation_ids": sorted(citations.get(c.id, set())), "selected": c.id in selected} for c in chunks if c.material_revision_id == material.current_revision_id]
        result.append(data)
    return {"materials": result, "active_scope": scope_dto(db, scope), "version": collection.version, "progress": progress_dto(db, collection, scope)}

class ScopeBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chunk_ids: list[str] = Field(min_length=1, max_length=1000)
    expected_version: int = Field(ge=1)

@router.post("/collections/{collection_id}/scope", status_code=201, response_model=ScopeResultDTO)
def save_scope(collection_id: str, body: ScopeBody, learner=Depends(get_learner), db=Depends(get_db)):
    collection = owned(db, Collection, collection_id, learner.id)
    if len(set(body.chunk_ids)) != len(body.chunk_ids):
        raise HTTPException(422, "duplicate_chunk_ids")
    chunks = db.scalars(select(Chunk).join(MaterialRevision, MaterialRevision.id == Chunk.material_revision_id).join(Material, Material.id == MaterialRevision.material_id).where(Chunk.id.in_(body.chunk_ids), Chunk.learner_id == learner.id, MaterialRevision.learner_id == learner.id, Material.learner_id == learner.id, Material.collection_id == collection.id, Material.current_revision_id == MaterialRevision.id, Material.archived.is_(False))).all()
    if {row.id for row in chunks} != set(body.chunk_ids):
        raise HTTPException(404, "not_found")
    version_claim(db, Collection, collection, body.expected_version)
    prior = active_scope(db, collection.id, learner.id)
    number = (db.scalar(select(func.max(ScopeRevision.revision_number)).where(ScopeRevision.collection_id == collection.id)) or 0) + 1
    if prior:
        prior.active = False
        db.flush()
    scope = ScopeRevision(learner_id=learner.id, collection_id=collection.id, revision_number=number)
    db.add(scope)
    db.flush()
    for index, chunk_id in enumerate(body.chunk_ids):
        db.add(ScopeItem(learner_id=learner.id, scope_revision_id=scope.id, chunk_id=chunk_id, position=index))
    db.flush()
    result = {"scope_revision": scope_dto(db, scope), "progress": progress_dto(db, collection, scope), "version": collection.version}
    db.commit()
    return result

class ReorderBody(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ordered_ids: list[str] = Field(max_length=1000)
    expected_version: int = Field(ge=1)

def reorder(db, rows, ids):
    if len(set(ids)) != len(ids) or set(ids) != {row.id for row in rows}:
        raise HTTPException(422, "complete_sibling_order_required")
    positions = {entity_id: index for index, entity_id in enumerate(ids)}
    for row in rows:
        row.position = positions[row.id]

@router.patch("/collections/{collection_id}/materials/reorder", response_model=OrderResultDTO)
def reorder_materials(collection_id: str, body: ReorderBody, learner=Depends(get_learner), db=Depends(get_db)):
    collection = owned(db, Collection, collection_id, learner.id)
    rows = db.scalars(select(Material).where(Material.collection_id == collection.id, Material.learner_id == learner.id, Material.archived.is_(False))).all()
    reorder(db, rows, body.ordered_ids)
    version_claim(db, Collection, collection, body.expected_version)
    db.commit()
    return {"ordered_ids": body.ordered_ids, "version": collection.version}

@router.patch("/collections/{collection_id}/materials/{material_id}/chunks/reorder", response_model=OrderResultDTO)
def reorder_chunks(collection_id: str, material_id: str, body: ReorderBody, learner=Depends(get_learner), db=Depends(get_db)):
    owned(db, Collection, collection_id, learner.id)
    material = owned(db, Material, material_id, learner.id)
    if material.collection_id != collection_id:
        raise HTTPException(404, "not_found")
    rows = db.scalars(select(Chunk).where(Chunk.material_revision_id == material.current_revision_id, Chunk.learner_id == learner.id)).all()
    reorder(db, rows, body.ordered_ids)
    version_claim(db, Material, material, body.expected_version)
    db.commit()
    return {"ordered_ids": body.ordered_ids, "version": material.version}

@router.get("/collections/{collection_id}/progress", response_model=ProgressDTO)
def collection_progress(collection_id: str, scope_revision_id: str | None = None, learner=Depends(get_learner), db=Depends(get_db)):
    collection = owned(db, Collection, collection_id, learner.id)
    scope = owned(db, ScopeRevision, scope_revision_id, learner.id) if scope_revision_id else active_scope(db, collection.id, learner.id)
    if scope and scope.collection_id != collection.id:
        raise HTTPException(404, "not_found")
    return progress_dto(db, collection, scope)

def calibration(events):
    valid = [row for row in events if row.correct is not None]
    if not valid:
        return {"sample_count": 0, "confidence": 0, "accuracy": 0, "gap": 0, "brier_score": None, "window": "last-30-days"}
    conf = sum((row.confidence - 1) / 4 for row in valid) / len(valid)
    acc = sum(bool(row.correct) for row in valid) / len(valid)
    return {"sample_count": len(valid), "confidence": round(conf * 100, 1), "accuracy": round(acc * 100, 1), "gap": round((conf - acc) * 100, 1), "brier_score": round(sum(((row.confidence - 1) / 4 - int(row.correct)) ** 2 for row in valid) / len(valid), 4), "window": "last-30-days"}

@router.get("/collections/{collection_id}/history", response_model=HistoryDTO)
def history(collection_id: str, cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), learner=Depends(get_learner), db=Depends(get_db)):
    from datetime import timedelta
    owned(db, Collection, collection_id, learner.id)
    rows = db.scalars(select(ProgressEvent).join(StudySession, StudySession.id == ProgressEvent.session_id).where(ProgressEvent.learner_id == learner.id, StudySession.learner_id == learner.id, StudySession.collection_id == collection_id, ProgressEvent.timestamp >= utcnow() - timedelta(days=30)).order_by(ProgressEvent.timestamp.desc())).all()
    return {"items": [{"id": row.id, "chunk_id": row.chunk_id, "concept_id": row.concept_id, "timestamp": iso(row.timestamp), "confidence": row.confidence, "correct": row.correct, "correctness": row.correctness, "reviewer": row.reviewer_json} for row in rows[cursor:cursor + limit]], "total": len(rows), "next_cursor": cursor + limit if cursor + limit < len(rows) else None, "calibration": calibration(rows)}

@router.get("/collections/{collection_id}/weak-spots", response_model=WeakSpotsDTO)
def weak_spots(collection_id: str, learner=Depends(get_learner), db=Depends(get_db)):
    from datetime import timedelta
    collection = owned(db, Collection, collection_id, learner.id)
    scope = active_scope(db, collection.id, learner.id)
    ids = list(db.scalars(select(ScopeItem.chunk_id).where(ScopeItem.scope_revision_id == scope.id, ScopeItem.learner_id == learner.id))) if scope else []
    rows = db.execute(select(ProgressEvent, Chunk, Concept).join(Chunk, Chunk.id == ProgressEvent.chunk_id).join(Concept, Concept.id == ProgressEvent.concept_id).where(ProgressEvent.learner_id == learner.id, Chunk.learner_id == learner.id, Concept.learner_id == learner.id, Chunk.id.in_(ids), ProgressEvent.timestamp >= utcnow() - timedelta(days=30), or_(ProgressEvent.correct.is_(False), ProgressEvent.correct.is_(None), ProgressEvent.confidence <= 2)).order_by(ProgressEvent.timestamp.desc()).limit(200)).all() if ids else []
    items, seen = [], set()
    for event, chunk, concept in rows:
        if concept.id in seen:
            continue
        seen.add(concept.id)
        review = db.scalar(select(ReviewState).where(ReviewState.learner_id == learner.id, ReviewState.chunk_id == chunk.id))
        items.append({"chunk_id": chunk.id, "title": chunk.title, "concept_id": concept.id, "concept": concept.text, "citation_ids": concept.citation_ids, "timestamp": iso(event.timestamp), "next_review_at": iso(review.next_review_at) if review else None})
    return {"items": items, "total": len(items), "scope_revision_id": scope.id if scope else None}

@router.get("/dashboard", response_model=DashboardDTO)
def dashboard(learner=Depends(get_learner), db=Depends(get_db)):
    from datetime import timedelta
    collections_rows = db.scalars(select(Collection).where(Collection.learner_id == learner.id, Collection.archived.is_(False)).order_by(Collection.position).limit(200)).all()
    collection_data = collection_dtos(db, collections_rows)
    recent = db.scalars(select(Material).where(Material.learner_id == learner.id, Material.archived.is_(False)).order_by(Material.created_at.desc()).limit(8)).all()
    events = db.scalars(select(ProgressEvent).where(ProgressEvent.learner_id == learner.id, ProgressEvent.timestamp >= utcnow() - timedelta(days=30))).all()
    due = db.scalar(select(func.count()).select_from(ReviewState).where(ReviewState.learner_id == learner.id, ReviewState.next_review_at <= utcnow()))
    resume = db.scalar(select(StudySession).where(StudySession.learner_id == learner.id, StudySession.status.not_in(["finished", "failed"])).order_by(StudySession.started_at.desc()).limit(1))
    connections = db.scalars(select(ProviderConnection).where(ProviderConnection.learner_id == learner.id)).all()
    return {"learner": learner_dto(learner), "collections_count": db.scalar(select(func.count()).select_from(Collection).where(Collection.learner_id == learner.id, Collection.archived.is_(False))), "due_count": due, "collections": collection_data, "scope_progress": [{"collection_id": c["id"], **c["progress"]} for c in collection_data], "resume": {"session_id": resume.id, "collection_id": resume.collection_id, "scope_revision_id": resume.scope_revision_id, "status": resume.status, "title": next((c.name for c in collections_rows if c.id == resume.collection_id), "Study")} if resume else None, "calibration": calibration(events), "recent_materials": material_dtos(db, recent), "connections": [{"provider": row.provider, "status": row.status} for row in connections], "mode": settings.app_mode, "demo_notice": "Offline demo — sample material" if settings.is_demo else None}

@router.get("/citations/{citation_id}", response_model=CitationDTO)
def citation(citation_id: str, learner=Depends(get_learner), db=Depends(get_db)):
    row = owned(db, Citation, citation_id, learner.id)
    revision = owned(db, MaterialRevision, row.revision_id, learner.id)
    material = owned(db, Material, revision.material_id, learner.id)
    return {"id": row.id, "excerpt": row.excerpt, "locator_kind": row.locator_kind, "locator": row.locator_json, "revision_id": revision.id, "material_id": material.id, "source_title": material.title, "source_language": revision.source_language, "source_url": revision.source_url, "viewer_url": f"/api/v1/material-revisions/{revision.id}/original" if revision.private_blob_key else None}

def job_dto(row):
    return {"id": row.id, "job_id": row.id, "kind": row.kind, "status": row.state, "state": row.state, "progress": row.progress, "attempts": row.attempts, "retryable": row.retryable, "error_code": row.error_code, "result": row.result, "created_at": iso(row.created_at)}

@router.get("/jobs/{job_id}", response_model=JobDTO)
def job(job_id: str, learner=Depends(get_learner), db=Depends(get_db)):
    return job_dto(owned(db, Job, job_id, learner.id))

@router.post("/jobs/{job_id}/retry", response_model=JobDTO)
def retry_job(job_id: str, learner=Depends(get_learner), db=Depends(get_db)):
    row = owned(db, Job, job_id, learner.id)
    if row.state in {"failed", "needs-attention"}:
        row.state = "queued"
        row.run_at = utcnow()
        row.error_code = None
        row.attempts = 0
        db.commit()
    return job_dto(row)

@router.get("/search", response_model=SearchDTO)
def search(q: str = Query(min_length=1, max_length=200), collection_id: str | None = None, cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), learner=Depends(get_learner), db=Depends(get_db)):
    if collection_id:
        owned(db, Collection, collection_id, learner.id)
    pattern = "%" + q.replace("%", "\\%").replace("_", "\\_") + "%"
    def filters(query):
        query = query.where(Material.learner_id == learner.id, Material.archived.is_(False), Collection.learner_id == learner.id, Collection.archived.is_(False))
        return query.where(Material.collection_id == collection_id) if collection_id else query
    material = filters(select(Material.id.label("id"), literal("material").label("type"), Material.title.label("title"), Material.collection_id.label("collection_id")).join(Collection, Material.collection_id == Collection.id).where(Material.title.ilike(pattern, escape="\\")))
    chunk = filters(select(Chunk.id.label("id"), literal("chunk").label("type"), Chunk.title.label("title"), Material.collection_id.label("collection_id")).join(MaterialRevision, Chunk.material_revision_id == MaterialRevision.id).join(Material, MaterialRevision.material_id == Material.id).join(Collection, Material.collection_id == Collection.id).where(Chunk.learner_id == learner.id, MaterialRevision.learner_id == learner.id, Material.current_revision_id == MaterialRevision.id, Chunk.title.ilike(pattern, escape="\\")))
    concept = filters(select(Concept.id.label("id"), literal("concept").label("type"), Concept.text.label("title"), Material.collection_id.label("collection_id")).join(Chunk, Concept.chunk_id == Chunk.id).join(MaterialRevision, Chunk.material_revision_id == MaterialRevision.id).join(Material, MaterialRevision.material_id == Material.id).join(Collection, Material.collection_id == Collection.id).where(Concept.learner_id == learner.id, Chunk.learner_id == learner.id, MaterialRevision.learner_id == learner.id, Material.current_revision_id == MaterialRevision.id, Concept.text.ilike(pattern, escape="\\")))
    citation = filters(select(Citation.id.label("id"), literal("citation").label("type"), Citation.excerpt.label("title"), Material.collection_id.label("collection_id")).join(MaterialRevision, Citation.revision_id == MaterialRevision.id).join(Material, MaterialRevision.material_id == Material.id).join(Collection, Material.collection_id == Collection.id).where(Citation.learner_id == learner.id, MaterialRevision.learner_id == learner.id, Material.current_revision_id == MaterialRevision.id, Citation.excerpt.ilike(pattern, escape="\\")))
    results = union_all(material, chunk, concept, citation).subquery()
    total = db.scalar(select(func.count()).select_from(results))
    rows = db.execute(select(results).order_by(results.c.type, results.c.id).offset(cursor).limit(limit)).mappings().all()
    return {"items": [{**dict(row), "title": row["title"][:500]} for row in rows], "total": total, "next_cursor": cursor + len(rows) if cursor + len(rows) < total else None}

@router.get("/notifications", response_model=NotificationListDTO)
def notifications(cursor: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200), learner=Depends(get_learner), db=Depends(get_db)):
    query = select(Notification).where(Notification.learner_id == learner.id)
    total = db.scalar(select(func.count()).select_from(query.subquery()))
    rows = db.scalars(query.order_by(Notification.created_at.desc()).offset(cursor).limit(limit)).all()
    return {"items": [{"id": row.id, "kind": row.kind, "title": row.title, "body": row.body, "entity_id": row.entity_id, "read_at": iso(row.read_at), "created_at": iso(row.created_at)} for row in rows], "total": total, "next_cursor": cursor + len(rows) if cursor + len(rows) < total else None}

@router.post("/notifications/{notification_id}/read", response_model=NoticeReadDTO)
def read_notice(notification_id: str, learner=Depends(get_learner), db=Depends(get_db)):
    row = owned(db, Notification, notification_id, learner.id)
    row.read_at = row.read_at or utcnow()
    db.commit()
    return {"id": row.id, "read_at": iso(row.read_at)}

@router.get("/me/export")
def export(learner=Depends(get_learner), db=Depends(get_db)):
    result = {"learner": learner_dto(learner), "exported_at": iso(utcnow()), "tables": {}}
    for cls in (Collection, Material, MaterialRevision, Chunk, Concept, Citation, ScopeRevision, ScopeItem, StudySession, SessionItem, ProgressEvent, TitleAssessment, ReviewState, Notification):
        data = []
        for row in db.scalars(select(cls).where(cls.learner_id == learner.id)):
            item = {}
            for col in cls.__table__.columns:
                if col.name in {"private_blob_key", "question_json_private"}:
                    continue
                value = getattr(row, col.name)
                item[col.name] = iso(value) if isinstance(value, datetime) else value
            data.append(item)
        result["tables"][cls.__tablename__] = data
    return result

class DeleteMeBody(BaseModel):
    confirmation: Literal["DELETE"]

@router.delete("/me", status_code=202, response_model=DeleteQueuedDTO)
def delete_me(body: DeleteMeBody, learner=Depends(get_learner), db=Depends(get_db)):
    job = enqueue(db, learner.id, "delete-learner", {}, f"delete-learner:{learner.id}")
    db.execute(update(Job).where(Job.learner_id == learner.id, Job.id != job.id, Job.state.in_(["queued", "running"])).values(state="cancelled", lease_owner=None, lease_until=None).execution_options(synchronize_session=False))
    for connection in db.scalars(select(ProviderConnection).where(ProviderConnection.learner_id == learner.id)):
        connection.status = "disconnected"
    for auth in db.scalars(select(AuthSession).where(AuthSession.learner_id == learner.id)):
        auth.revoked = True
    db.commit()
    return {"job_id": job.id, "state": job.state}

@register("delete-learner")
def delete_learner(db, job):
    learner_id = job.learner_id
    # Close DB transaction before remote OAuth/object storage operations.
    from types import SimpleNamespace
    from .storage import get_storage
    from .sources.drive import revoke_connection
    from .jobs import assert_lease
    keys = list(db.scalars(select(MaterialRevision.private_blob_key).where(MaterialRevision.learner_id == learner_id, MaterialRevision.private_blob_key.is_not(None))))
    connections = list(db.scalars(select(ProviderConnection).where(ProviderConnection.learner_id == learner_id)))
    revocations = []
    for row in connections:
        if row.provider == "drive":
            revocations.append(SimpleNamespace(encrypted_credentials=row.encrypted_credentials, status="disconnected"))
        row.encrypted_credentials = None
        row.status = "disconnected"
    db.commit()
    revoked = all([revoke_connection(row) for row in revocations])
    storage = get_storage()
    for key in keys:
        storage.delete(learner_id, key)
    assert_lease(db, job)
    # Retain a non-content completion receipt; remove children in dependency order.
    for cls in (OutboxEvent, AuthSession, SourceWriteReceipt, ProviderConnection, Notification, ReviewState, TitleAssessment, ProgressEvent, SessionItem, StudySession, ScopeItem, ScopeRevision, ConceptRelation, Concept, Citation, Chunk, MaterialRevision, Material, Collection):
        db.execute(delete(cls).where(cls.learner_id == learner_id))
    db.execute(delete(Job).where(Job.learner_id == learner_id, Job.id != job.id))
    learner = db.get(Learner, learner_id)
    if learner:
        learner.display_name = "Deleted learner"
        learner.oidc_subject = None
        learner.oidc_issuer = None
        learner.ui_locale = "en"
        learner.study_locale = "en"
        learner.speech_locale = "en-GB"
        learner.timezone = "UTC"
        learner.preferences = {"deleted": True}
    return {"deleted": True, "provider_revocation": "confirmed" if revoked else "provider-unconfirmed"}
