"""Owned, versioned learning endpoints backed by durable jobs."""
from typing import Literal
from datetime import datetime

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select, update

from .auth import get_learner
from .db import get_db, utcnow, as_utc
from .jobs import enqueue
from .models import Collection, Learner, ScopeRevision, ScopeItem, StudySession, SessionItem, Job, ProgressEvent, ReviewState, Chunk, MaterialRevision
from .sessions import owned, session_dto, public_turn, queue_summary
from .settings import settings
from .review import local_due

router = APIRouter()


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Start(StrictInput):
    collection_id: str
    scope_revision_id: str
    mode: Literal["study", "review"] = "study"


class Answer(StrictInput):
    item_id: str
    answer: str = Field(min_length=1, max_length=12000)
    confidence: int = Field(ge=1, le=5, strict=True)
    expected_version: int = Field(ge=1)
    voice: bool = False


class Advance(StrictInput):
    expected_version: int = Field(ge=1)


class CoverageDTO(BaseModel):
    critical_ids: list[str]
    demonstrated_ids: list[str]
    complete: bool
    evidence_event_ids: list[str]


class FeedbackDTO(BaseModel):
    item_id: str
    correctness: Literal['correct', 'incorrect', 'partial', 'uncertain']
    confidence: int
    missing_parts: list[str]
    guessing_signal: Literal['supported', 'unsupported', 'unknown']
    feedback: str
    title_complete: bool
    rationale: str
    evidence_event_ids: list[str]
    citation_ids: list[str]
    critical_coverage: CoverageDTO
    demo: bool
    provider_version: str
    prompt_version: str
    voice: bool


class SessionDTO(BaseModel):
    id: str
    status: str
    version: int
    collection_id: str
    scope_revision_id: str
    mode: Literal['study', 'review']
    current_item_id: str | None
    generation_locale: str
    turn_count: int
    job_id: str | None = None
    demo: bool


class PublicTurnDTO(BaseModel):
    session_id: str
    status: str
    version: int
    item_id: str
    question: str
    teaching: str
    citation_ids: list[str]
    concept_id: str
    chunk_id: str
    generation_locale: str
    answer_state: str
    feedback: FeedbackDTO | None
    demo: bool = False
    voice_turn_count: int = 0
    job_id: str | None = None
    job_state: str | None = None
    error_code: str | None = None
    retryable: bool | None = None


class PendingTurnDTO(SessionDTO):
    voice_turn_count: int = 0
    job_state: str | None = None
    error_code: str | None = None
    retryable: bool | None = None


class SessionStateDTO(SessionDTO):
    current_turn: PublicTurnDTO | None
    voice_turn_count: int


class TitleDTO(BaseModel):
    id: str
    title: str


class CalibrationDTO(BaseModel):
    sample_count: int
    mean_confidence: float | None
    accuracy: float | None
    gap: float | None
    brier_score: float | None


class SummaryDTO(BaseModel):
    session_id: str
    completed_titles: list[TitleDTO]
    remaining_titles: list[TitleDTO]
    calibration: CalibrationDTO
    sample_count: int
    citation_ids: list[str]
    demo: bool
    study_locale: str


class DueItemDTO(BaseModel):
    chunk_id: str
    title: str
    collection_id: str
    stage: int
    next_review_at: datetime
    local_due: str
    needs_attention: bool


class DueDTO(BaseModel):
    items: list[DueItemDTO]
    total: int


def key_for(action, session_id, key):
    if not key or len(key) > 120:
        raise HTTPException(400, "A stable Idempotency-Key (maximum 120 characters) is required")
    return f"{action}:{session_id}:{key}"


def prior_job(db, learner_id, key, payload=None):
    job = db.scalar(select(Job).where(Job.learner_id == learner_id, Job.idempotency_key == key))
    if job and payload:
        for name in payload:
            if job.payload.get(name) != payload[name]:
                raise HTTPException(409, "Idempotency-Key already used for a different request")
    return job


def result(session, job=None):
    return {**session_dto(session), "job_id": job.id if job else None, "demo": settings.app_mode == "demo"}


def claim(db, session, version, allowed, next_status):
    changed = db.execute(update(StudySession).where(StudySession.id == session.id,
        StudySession.learner_id == session.learner_id, StudySession.version == version,
        StudySession.status.in_(allowed)).values(status=next_status, version=StudySession.version + 1))
    if changed.rowcount != 1:
        raise HTTPException(409, "Session changed; refresh before submitting")
    db.refresh(session)


@router.post("/sessions", status_code=202, response_model=SessionDTO)
def start_session(body: Start, db=Depends(get_db), learner=Depends(get_learner), idempotency_key: str | None = Header(None)):
    collection = owned(db, Collection, body.collection_id, learner.id)
    scope = owned(db, ScopeRevision, body.scope_revision_id, learner.id)
    if collection.archived or scope.collection_id != collection.id:
        raise HTTPException(404, "Not found")
    if not db.scalar(select(ScopeItem.id).where(ScopeItem.scope_revision_id == scope.id, ScopeItem.learner_id == learner.id)):
        raise HTTPException(422, "Select at least one titled section")
    key = key_for("start", collection.id, idempotency_key) if idempotency_key else None
    prior = prior_job(db, learner.id, key, {"scope_revision_id": scope.id, "mode": body.mode}) if key else None
    if prior:
        return result(owned(db, StudySession, prior.payload["session_id"], learner.id), prior)
    session = StudySession(learner_id=learner.id, collection_id=collection.id, scope_revision_id=scope.id,
                           mode=body.mode, status="generating", generation_locale=learner.study_locale)
    db.add(session)
    db.flush()
    if body.mode == "review":
        session.summary_json = {"review_chunk_ids": list(db.scalars(select(ReviewState.chunk_id).join(
            ScopeItem, ScopeItem.chunk_id == ReviewState.chunk_id).where(ReviewState.learner_id == learner.id,
            ScopeItem.learner_id == learner.id, ScopeItem.scope_revision_id == scope.id,
            ReviewState.next_review_at <= session.started_at)))}
    job = enqueue(db, learner.id, "session.generate", {"session_id": session.id, "scope_revision_id": scope.id, "mode": body.mode}, key)
    db.commit()
    return result(session, job)


@router.get("/sessions/{session_id}", response_model=SessionStateDTO)
def get_session(session_id: str, db=Depends(get_db), learner=Depends(get_learner)):
    session = owned(db, StudySession, session_id, learner.id)
    item = owned(db, SessionItem, session.current_item_id, learner.id) if session.current_item_id else None
    count = sum(bool(e.reviewer_json.get('voice')) for e in db.scalars(select(ProgressEvent).where(
        ProgressEvent.learner_id == learner.id, ProgressEvent.session_id == session.id)))
    return {**result(session), "current_turn": public_turn(session, item) if item else None, "voice_turn_count": count}


@router.get("/sessions/{session_id}/next", response_model=PublicTurnDTO | PendingTurnDTO,
            responses={202: {'model': PublicTurnDTO | PendingTurnDTO}})
def next_turn(session_id: str, response: Response, db=Depends(get_db), learner=Depends(get_learner)):
    session = owned(db, StudySession, session_id, learner.id)
    latest_job = db.scalar(select(Job).where(Job.learner_id == learner.id, Job.entity_id == session.id,
        Job.kind.in_(['session.generate', 'session.assess', 'session.summary', 'session.finished']))
                          .order_by(Job.created_at.desc(), Job.id.desc()))
    job_info = {"job_id": latest_job.id, "job_state": latest_job.state, "error_code": latest_job.error_code,
                "retryable": latest_job.retryable} if latest_job else {}
    blocked = latest_job and latest_job.state in {"needs-attention", "failed"} and session.status in {"generating", "reviewing", "finishing"}
    if session.status in {"generating", "reviewing", "finishing"}:
        response.status_code = 202
    if not session.current_item_id:
        dto = {**result(session), **job_info}
    else:
        item = owned(db, SessionItem, session.current_item_id, learner.id)
        dto = {**public_turn(session, item), "demo": settings.app_mode == "demo", **job_info}
    if blocked:
        response.status_code = 200
        dto["status"] = "needs_attention"
    dto['voice_turn_count'] = sum(bool(e.reviewer_json.get('voice')) for e in db.scalars(select(ProgressEvent).where(
        ProgressEvent.learner_id == learner.id, ProgressEvent.session_id == session.id)))
    return dto


@router.post("/sessions/{session_id}/answer", status_code=202, response_model=SessionDTO)
def answer(session_id: str, body: Answer, db=Depends(get_db), learner=Depends(get_learner), idempotency_key: str | None = Header(None)):
    session = owned(db, StudySession, session_id, learner.id)
    key = key_for("answer", session_id, idempotency_key)
    payload = {"session_id": session_id, "item_id": body.item_id, "answer": body.answer,
               "confidence": body.confidence, "voice": body.voice, "idempotency_key": key}
    prior = prior_job(db, learner.id, key, payload)
    if prior:
        return result(session, prior)
    item = owned(db, SessionItem, body.item_id, learner.id)
    if item.session_id != session.id or session.current_item_id != item.id:
        raise HTTPException(404, "Not found")
    if not body.answer.strip():
        raise HTTPException(422, "Answer cannot be blank")
    if item.answer_state != "pending":
        raise HTTPException(409, "This item already has an answer")
    claim(db, session, body.expected_version, ["awaiting_answer"], "reviewing")
    item.answer_state = "reviewing"
    job = enqueue(db, learner.id, "session.assess", payload, key)
    db.commit()
    return result(session, job)


@router.post("/sessions/{session_id}/advance", status_code=202, response_model=SessionDTO)
def advance(session_id: str, body: Advance, db=Depends(get_db), learner=Depends(get_learner), idempotency_key: str | None = Header(None)):
    session = owned(db, StudySession, session_id, learner.id)
    key = key_for("advance", session_id, idempotency_key)
    prior = prior_job(db, learner.id, key)
    if prior:
        return result(session, prior)
    claim(db, session, body.expected_version, ["feedback"], "generating")
    session.current_item_id = None
    job = enqueue(db, learner.id, "session.generate", {"session_id": session.id}, key)
    db.commit()
    return result(session, job)


@router.post("/sessions/{session_id}/finish", status_code=202, response_model=SessionDTO)
def finish(session_id: str, body: Advance, db=Depends(get_db), learner=Depends(get_learner), idempotency_key: str | None = Header(None)):
    session = owned(db, StudySession, session_id, learner.id)
    key = key_for("finish", session_id, idempotency_key)
    prior = prior_job(db, learner.id, key)
    if prior:
        return result(session, prior)
    if session.status in {"finishing", "finished"}:
        return result(session)
    # Do not discard an in-flight grading result. Learners may explicitly finish other states.
    claim(db, session, body.expected_version, ["feedback", "awaiting_answer", "generating"], "interrupted")
    job = queue_summary(db, session)
    enqueue(db, learner.id, "session.summary", {"session_id": session.id}, key)
    db.commit()
    return result(session, job)


@router.get("/sessions/{session_id}/summary", response_model=SummaryDTO | SessionDTO,
            responses={202: {'model': SessionDTO}})
def summary(session_id: str, response: Response, db=Depends(get_db), learner=Depends(get_learner)):
    session = owned(db, StudySession, session_id, learner.id)
    if session.status != "finished":
        response.status_code = 202
        return result(session)
    return session.summary_json


@router.get("/review/due", response_model=DueDTO)
def due_review(collection_id: str | None = None, db=Depends(get_db), learner=Depends(get_learner)):
    query = select(ReviewState, Chunk, MaterialRevision).join(Chunk, ReviewState.chunk_id == Chunk.id).join(
        MaterialRevision, Chunk.material_revision_id == MaterialRevision.id).where(ReviewState.learner_id == learner.id,
        Chunk.learner_id == learner.id, MaterialRevision.learner_id == learner.id, ReviewState.next_review_at <= utcnow())
    if collection_id:
        owned(db, Collection, collection_id, learner.id)
        query = query.where(MaterialRevision.collection_id == collection_id)
    rows = db.execute(query.order_by(ReviewState.next_review_at).limit(200)).all()
    return {"items": [{"chunk_id": chunk.id, "title": chunk.title, "collection_id": rev.collection_id,
        "stage": state.stage, "next_review_at": as_utc(state.next_review_at), "local_due": local_due(state.next_review_at, learner.timezone),
        "needs_attention": state.needs_attention} for state, chunk, rev in rows], "total": len(rows)}
