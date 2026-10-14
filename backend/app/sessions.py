"""Durable session handlers. Public DTOs are deliberately separate from rubrics."""
import hashlib
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from .db import utcnow, as_utc
from .jobs import enqueue, register, NeedsAttention, RetryableJobError, assert_lease
from .llm import get_provider, InvalidModelOutput, ProviderUnavailable
from .models import (StudySession, SessionItem, ScopeRevision, ScopeItem, Chunk, Concept,
                     Citation, MaterialRevision, ProgressEvent, TitleAssessment, Learner,
                     OutboxEvent, ReviewState)
from .review import coverage, calibration, apply_review
from .settings import settings


def owned(db, model, identifier, learner_id):
    row = db.scalar(select(model).where(model.id == identifier, model.learner_id == learner_id))
    if row is None:
        raise HTTPException(404, "Not found")
    return row


def session_dto(session):
    return {"id": session.id, "status": session.status, "version": session.version,
            "collection_id": session.collection_id, "scope_revision_id": session.scope_revision_id,
            "mode": session.mode, "current_item_id": session.current_item_id,
            "generation_locale": session.generation_locale, "turn_count": session.turn_count}


def public_turn(session, item):
    return {"session_id": session.id, "status": session.status, "version": session.version,
            "item_id": item.id, "question": item.public_question, "teaching": item.teaching,
            "citation_ids": item.citation_ids, "concept_id": item.concept_id, "chunk_id": item.chunk_id,
            "generation_locale": item.generation_locale, "answer_state": item.answer_state,
            "feedback": item.feedback_json or None, "demo": item.provider_version == "demo-v1"}


def model_call(kind, context):
    try:
        provider = get_provider()
        return provider, provider.generate(kind, context)
    except ProviderUnavailable as exc:
        if exc.retryable:
            raise RetryableJobError(exc.code) from None
        raise NeedsAttention(exc.code) from None
    except InvalidModelOutput:
        raise NeedsAttention("invalid_model_output") from None


def scope_chunks(db, session):
    scope = owned(db, ScopeRevision, session.scope_revision_id, session.learner_id)
    if scope.collection_id != session.collection_id:
        raise InvalidModelOutput("Session scope mismatch")
    return list(db.scalars(select(Chunk).join(ScopeItem, ScopeItem.chunk_id == Chunk.id).where(
        ScopeItem.scope_revision_id == scope.id, ScopeItem.learner_id == session.learner_id,
        Chunk.learner_id == session.learner_id).order_by(ScopeItem.position)))


def title_events(db, session, chunk_id):
    query = select(ProgressEvent).join(StudySession, ProgressEvent.session_id == StudySession.id).where(
        ProgressEvent.learner_id == session.learner_id, StudySession.learner_id == session.learner_id,
        ProgressEvent.chunk_id == chunk_id, StudySession.scope_revision_id == session.scope_revision_id)
    if session.mode == "review":
        query = query.where(ProgressEvent.session_id == session.id)
    return list(db.scalars(query.order_by(ProgressEvent.timestamp, ProgressEvent.id)))


def source_context(db, session, concept):
    chunk = owned(db, Chunk, concept.chunk_id, session.learner_id)
    if chunk.id not in {c.id for c in scope_chunks(db, session)}:
        raise InvalidModelOutput("Concept outside immutable scope")
    revision = owned(db, MaterialRevision, chunk.material_revision_id, session.learner_id)
    if revision.collection_id != session.collection_id:
        raise InvalidModelOutput("Foreign collection source")
    citations = list(db.scalars(select(Citation).where(Citation.learner_id == session.learner_id,
                        Citation.revision_id == revision.id, Citation.id.in_(concept.citation_ids))))
    if not citations:
        raise InvalidModelOutput("No supported source citation")
    for cite in citations:
        if hashlib.sha256(cite.excerpt.encode()).hexdigest() != cite.excerpt_hash or cite.excerpt not in revision.extracted_text:
            raise InvalidModelOutput("Citation does not resolve to original source")
    prior = list(db.scalars(select(ProgressEvent).where(ProgressEvent.learner_id == session.learner_id,
        ProgressEvent.session_id == session.id, ProgressEvent.concept_id == concept.id)
        .order_by(ProgressEvent.timestamp.desc()).limit(3)))
    prior_context = [{"event_id": e.id, "answer": e.answer, "confidence": e.confidence,
        "correctness": e.correctness, "missing_parts": e.reviewer_json.get("missing_parts", []),
        "feedback": e.reviewer_json.get("feedback", ""), "citation_ids": e.reviewer_json.get("citation_ids", []),
        "voice": bool(e.reviewer_json.get("voice"))} for e in reversed(prior)]
    return {"chunk_id": chunk.id, "chunk_title": chunk.title, "source_revision_id": revision.id,
            "study_locale": session.generation_locale, "speech_locale": db.get(Learner, session.learner_id).speech_locale,
            "source_language": revision.source_language, "mode": session.mode,
            "demo_fixture": revision.metadata_json.get("demo_fixture", False),
            "prior_attempts": prior_context, "targeted_followup": bool(prior_context),
            "concepts": [{"id": concept.id, "text": concept.text, "citation_ids": concept.citation_ids}],
            "citations": [{"id": c.id, "excerpt": c.excerpt, "locator": c.locator_json} for c in citations]}


def choose_concept(db, session):
    for chunk in scope_chunks(db, session):
        if session.mode == "review":
            # Pin the due set at session start: advancing must not re-enrol future due work.
            if chunk.id not in session.summary_json.get("review_chunk_ids", []):
                continue
        concepts = list(db.scalars(select(Concept).where(Concept.learner_id == session.learner_id,
                                          Concept.chunk_id == chunk.id).order_by(Concept.position)))
        critical = {c.id for c in concepts if c.critical}
        evidence = coverage(critical, title_events(db, session, chunk.id))
        if evidence["complete"]:
            accepted = db.scalar(select(TitleAssessment).where(TitleAssessment.learner_id == session.learner_id,
                TitleAssessment.scope_revision_id == session.scope_revision_id, TitleAssessment.chunk_id == chunk.id)
                .order_by(TitleAssessment.created_at.desc(), TitleAssessment.id.desc()))
            if accepted and accepted.complete:
                continue
            # Coverage is a guard, not a substitute for the Reviewer's verdict.
            if concepts:
                return concepts[0]
        for concept in concepts:
            if concept.critical and concept.id not in evidence["demonstrated_ids"]:
                return concept
    return None


def queue_summary(db, session):
    if session.status in {"finishing", "finished"}:
        return None
    session.status = "finishing"
    session.finished_at = utcnow()
    session.version += 1
    key = f"summary:{session.id}"
    existing = db.scalar(select(OutboxEvent).where(OutboxEvent.aggregate_id == session.id,
        OutboxEvent.event_type == "session.finished", OutboxEvent.learner_id == session.learner_id))
    if not existing:
        db.add(OutboxEvent(learner_id=session.learner_id, aggregate_id=session.id,
                          aggregate_version=session.version, event_type="session.finished", payload={"session_id": session.id}))
    return enqueue(db, session.learner_id, "session.summary", {"session_id": session.id}, idempotency_key=key)


def generate_turn(db, job):
    session = owned(db, StudySession, job.payload["session_id"], job.learner_id)
    if session.status != "generating":
        return {"session_id": session.id, "status": session.status}
    concept = choose_concept(db, session)
    if not concept:
        queue_summary(db, session)
        return {"session_id": session.id, "status": "finishing"}
    session.generation_locale = db.get(Learner, job.learner_id).study_locale
    context = source_context(db, session, concept)
    session_id, version, concept_id, chunk_id = session.id, session.version, concept.id, concept.chunk_id
    db.commit()  # Provider latency must not hold a DB transaction/row lock.
    provider, result = model_call("turn", context)
    assert_lease(db, job)
    session = owned(db, StudySession, session_id, job.learner_id)
    if session.status != "generating" or session.version != version:
        return {"session_id": session_id, "status": session.status}
    previous = db.scalar(select(SessionItem).where(SessionItem.session_id == session.id,
                      SessionItem.learner_id == session.learner_id, SessionItem.position == session.turn_count))
    if previous:
        item = previous
    else:
        item = SessionItem(learner_id=session.learner_id, session_id=session.id, concept_id=concept_id,
            chunk_id=chunk_id, question_json_private={**result, "_metadata": {
                "prompt_version": "quizzer-v5", "provider": provider.name,
                "source_revision_id": context['source_revision_id'], "source_language": context['source_language'],
                "study_locale": context['study_locale'], "speech_locale": context['speech_locale']}}, public_question=result["question"],
            teaching=result["teaching"], citation_ids=result["citation_ids"], position=session.turn_count,
            generation_locale=context["study_locale"], provider_version=provider.version)
        db.add(item)
        db.flush()
    session.current_item_id = item.id
    session.status = "awaiting_answer"
    session.version += 1
    return {"session_id": session.id, "item_id": item.id}


def assess_answer(db, job):
    session = owned(db, StudySession, job.payload["session_id"], job.learner_id)
    item = owned(db, SessionItem, job.payload["item_id"], job.learner_id)
    if item.session_id != session.id:
        raise InvalidModelOutput("Foreign session item")
    existing = db.scalar(select(ProgressEvent).where(ProgressEvent.learner_id == job.learner_id,
        ProgressEvent.idempotency_key == job.payload["idempotency_key"]))
    if existing:
        return {"session_id": session.id, "event_id": existing.id}
    if session.status != "reviewing" or session.current_item_id != item.id or item.answer_state != "reviewing":
        raise InvalidModelOutput("Attempt no longer current")
    concept = owned(db, Concept, item.concept_id, job.learner_id)
    context = source_context(db, session, concept)
    context["study_locale"] = item.generation_locale
    events = title_events(db, session, item.chunk_id)
    critical = set(db.scalars(select(Concept.id).where(Concept.chunk_id == item.chunk_id,
                     Concept.learner_id == job.learner_id, Concept.critical.is_(True))))
    prior_coverage = coverage(critical, events)
    event_id = str(uuid4())
    context.update({"item_id": item.id, "answer": job.payload["answer"], "confidence": job.payload["confidence"],
        "question": item.public_question, "expected_answer": item.question_json_private["expected_answer"],
        "evidence_event_ids": [e.id for e in events] + [event_id], "critical_concept_ids": sorted(critical),
        "demonstrated_concept_ids": prior_coverage["demonstrated_ids"],
        "prior_evidence": [{"id": e.id, "concept_id": e.concept_id, "correctness": e.correctness,
            "confidence": e.confidence, "guessing_signal": e.reviewer_json.get("guessing_signal", "unknown"),
            "citation_ids": e.reviewer_json.get("citation_ids", [])} for e in events],
        "coverage_ready": critical <= set(prior_coverage["demonstrated_ids"]) | {concept.id},
        "demo_accepted_answers": [concept.text] if context.get("demo_fixture") else []})
    session_id, item_id, version = session.id, item.id, session.version
    db.commit()
    provider, verdict = model_call("assessment", context)
    assert_lease(db, job)
    session = owned(db, StudySession, session_id, job.learner_id)
    item = owned(db, SessionItem, item_id, job.learner_id)
    if session.status != "reviewing" or session.version != version:
        raise InvalidModelOutput("Attempt changed during assessment")
    correct = True if verdict["correctness"] == "correct" else None if verdict["correctness"] == "uncertain" else False
    event = ProgressEvent(id=event_id, learner_id=job.learner_id, concept_id=concept.id, chunk_id=item.chunk_id,
        session_id=session.id, item_id=item.id, confidence=job.payload["confidence"], correct=correct,
        correctness=verdict["correctness"], answer=job.payload["answer"], timestamp=utcnow(), reviewer_json=verdict,
        idempotency_key=job.payload["idempotency_key"], answer_locale=item.generation_locale, provider_version=provider.version)
    db.add(event)
    db.flush()
    evidence = coverage(critical, events + [event])
    complete = verdict["title_complete"] and evidence["complete"] and correct is True
    # Completion requires Reviewer to cite the exact trusted coverage evidence, not invented history.
    complete = complete and set(evidence["evidence_event_ids"]) <= set(verdict["evidence_event_ids"])
    verdict = {**verdict, "title_complete": bool(complete), "critical_coverage": evidence,
               "demo": provider.name == "offline-fixture", "provider_version": provider.version,
               "prompt_version": "reviewer-v4", "voice": job.payload.get("voice", False),
               "source_revision_id": context['source_revision_id'], "source_language": context['source_language'],
               "study_locale": item.generation_locale, "speech_locale": context['speech_locale']}
    event.reviewer_json = verdict
    db.add(TitleAssessment(learner_id=job.learner_id, chunk_id=item.chunk_id, scope_revision_id=session.scope_revision_id,
        complete=bool(complete), rationale=verdict["rationale"], evidence_event_ids=evidence["evidence_event_ids"], critical_coverage=evidence))
    if complete:
        apply_review(db, event, True, initial=session.mode == "study")
    elif session.mode == "review" and correct is False:
        apply_review(db, event, False)
    item.feedback_json = verdict
    item.answer_state = "answered"
    session.status = "feedback"
    session.turn_count += 1
    session.version += 1
    return {"session_id": session.id, "event_id": event.id, "title_complete": bool(complete)}


def summarize(db, job):
    session = owned(db, StudySession, job.payload["session_id"], job.learner_id)
    if session.status == "finished":
        return {"session_id": session.id}
    chunks = scope_chunks(db, session)
    completed, remaining = [], []
    for chunk in chunks:
        assessment = db.scalar(select(TitleAssessment).where(TitleAssessment.learner_id == session.learner_id,
            TitleAssessment.scope_revision_id == session.scope_revision_id, TitleAssessment.chunk_id == chunk.id)
            .order_by(TitleAssessment.created_at.desc(), TitleAssessment.id.desc()))
        (completed if assessment and assessment.complete else remaining).append({"id": chunk.id, "title": chunk.title})
    events = list(db.scalars(select(ProgressEvent).where(ProgressEvent.session_id == session.id,
                                                       ProgressEvent.learner_id == session.learner_id)))
    session.summary_json = {"session_id": session.id, "completed_titles": completed, "remaining_titles": remaining,
        "calibration": calibration(events), "sample_count": calibration(events)["sample_count"],
        "citation_ids": sorted({cid for e in events for cid in e.reviewer_json.get("citation_ids", [])}),
        "demo": settings.app_mode == 'demo', "study_locale": session.generation_locale}
    session.status = "finished"
    session.version += 1
    for outbox in db.scalars(select(OutboxEvent).where(OutboxEvent.learner_id == session.learner_id,
        OutboxEvent.aggregate_id == session.id, OutboxEvent.event_type == "session.finished")):
        outbox.processed_at = utcnow()
    return {"session_id": session.id, "summary_ready": True}


register("session.generate", generate_turn)
register("session.assess", assess_answer)
register("session.summary", summarize)
register("session.finished", summarize)
