"""Synthetic source fixtures only; no external calls or learner data."""
from datetime import datetime, timezone, timedelta
from types import SimpleNamespace
import hashlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db, utcnow
from app.auth import get_learner
from app.models import (Learner, Collection, Material, MaterialRevision, Chunk, Concept, Citation,
                        ScopeRevision, ScopeItem, StudySession, SessionItem, ProgressEvent, Job, ReviewState)
from app.learning_api import router
from app.sessions import generate_turn, assess_answer, summarize, public_turn
from app.review import coverage, calibration, schedule, local_due, apply_review
from app.llm import DemoProvider, OpenAIProvider, ProviderUnavailable, InvalidModelOutput, validate_output
from app.jobs import WORKER_ID


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr("app.sessions.get_provider", lambda: DemoProvider())
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    with factory() as db:
        learner = Learner(id="learner", is_demo=True, study_locale="en")
        foreign = Learner(id="foreign", is_demo=True)
        db.add_all([learner, foreign]); db.flush()
        collection = Collection(id="collection", learner_id=learner.id, name="Synthetic")
        db.add(collection); db.flush()
        material = Material(id="material", learner_id=learner.id, collection_id=collection.id, title="Memory", status="ready")
        db.add(material); db.flush()
        text = "Retrieval practice strengthens recall. Spacing practice reduces forgetting."
        revision = MaterialRevision(id="revision", learner_id=learner.id, material_id=material.id, collection_id=collection.id,
            content_hash=hashlib.sha256(text.encode()).hexdigest(), extracted_text=text, source_language="en", metadata_json={"demo_fixture": True})
        db.add(revision); db.flush()
        chunk = Chunk(id="chunk", learner_id=learner.id, material_revision_id=revision.id, title="Memory", text=text)
        db.add(chunk); db.flush()
        for index, sentence in enumerate(text.split(". ")):
            sentence = sentence.rstrip(".") + "."
            cite = Citation(id=f"cite{index}", learner_id=learner.id, revision_id=revision.id,
                locator_kind="text", locator_json={"line_start": index + 1, "line_end": index + 1},
                excerpt=sentence, excerpt_hash=hashlib.sha256(sentence.encode()).hexdigest())
            concept = Concept(id=f"concept{index}", learner_id=learner.id, chunk_id=chunk.id,
                text=sentence, citation_ids=[cite.id], critical=True, position=index)
            db.add_all([cite, concept])
        scope = ScopeRevision(id="scope", learner_id=learner.id, collection_id=collection.id, revision_number=1)
        db.add(scope); db.flush()
        db.add(ScopeItem(learner_id=learner.id, scope_revision_id=scope.id, chunk_id=chunk.id, position=0))
        db.commit()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    def database():
        with factory() as db:
            yield db
    def principal():
        with factory() as db:
            return db.get(Learner, "learner")
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_learner] = principal
    with TestClient(app) as client:
        yield client, factory, app
    engine.dispose()


def run_job(factory, job_id):
    with factory() as db:
        job = db.get(Job, job_id)
        job.state = "running"
        job.lease_owner = WORKER_ID
        job.lease_until = utcnow() + timedelta(seconds=300)
        db.commit()
        handlers = {"session.generate": generate_turn, "session.assess": assess_answer, "session.summary": summarize}
        job.result = handlers[job.kind](db, job)
        job.state = "succeeded"
        db.commit()
        return job.result


def start(env):
    client, factory, _ = env
    response = client.post("/api/v1/sessions", json={"collection_id": "collection", "scope_revision_id": "scope", "mode": "study"}, headers={"Idempotency-Key": "start"})
    assert response.status_code == 202
    session = response.json()
    run_job(factory, session["job_id"])
    return session["id"]


def test_complete_scope_coverage_and_idempotent_summary(env):
    client, factory, _ = env
    sid = start(env)
    for index in range(2):
        turn = client.get(f"/api/v1/sessions/{sid}/next").json()
        assert "expected_answer" not in str(turn) and "question_json_private" not in str(turn)
        with factory() as db:
            expected = db.get(Concept, turn["concept_id"]).text
            before = db.query(SessionItem).count()
        assert client.get(f"/api/v1/sessions/{sid}/next").json() == turn
        with factory() as db:
            assert db.query(SessionItem).count() == before
        payload = {"item_id": turn["item_id"], "answer": expected, "confidence": 5, "expected_version": turn["version"]}
        answer = client.post(f"/api/v1/sessions/{sid}/answer", json=payload, headers={"Idempotency-Key": f"answer{index}"})
        assert answer.status_code == 202
        job_id = answer.json()["job_id"]
        run_job(factory, job_id)
        assert client.post(f"/api/v1/sessions/{sid}/answer", json=payload, headers={"Idempotency-Key": f"answer{index}"}).json()["job_id"] == job_id
        feedback = client.get(f"/api/v1/sessions/{sid}/next").json()
        assert feedback["feedback"]["title_complete"] is (index == 1)
        advance = client.post(f"/api/v1/sessions/{sid}/advance", json={"expected_version": feedback["version"]}, headers={"Idempotency-Key": f"advance{index}"})
        assert advance.status_code == 202
        run_job(factory, advance.json()["job_id"])
    with factory() as db:
        summary_job = db.scalar(select(Job).where(Job.kind == "session.summary"))
        summary_id = summary_job.id
        assert db.query(ProgressEvent).count() == 2
    run_job(factory, summary_id)
    result = client.get(f"/api/v1/sessions/{sid}/summary").json()
    assert len(result["completed_titles"]) == 1
    assert result["calibration"]["sample_count"] == 2
    run_job(factory, summary_id)


def test_confidence_tenant_version_and_key_guards(env):
    client, factory, app = env
    sid = start(env)
    turn = client.get(f"/api/v1/sessions/{sid}/next").json()
    payload = {"item_id": turn["item_id"], "answer": "test", "confidence": 0, "expected_version": turn["version"]}
    assert client.post(f"/api/v1/sessions/{sid}/answer", json=payload, headers={"Idempotency-Key": "bad"}).status_code == 422
    payload["confidence"] = 5
    payload["expected_version"] = 999
    assert client.post(f"/api/v1/sessions/{sid}/answer", json=payload, headers={"Idempotency-Key": "bad"}).status_code == 409
    payload["expected_version"] = turn["version"]
    assert client.post(f"/api/v1/sessions/{sid}/answer", json=payload).status_code == 400
    response = client.post(f"/api/v1/sessions/{sid}/answer", json=payload, headers={"Idempotency-Key": "valid"})
    assert response.status_code == 202
    payload["answer"] = "different"
    assert client.post(f"/api/v1/sessions/{sid}/answer", json=payload, headers={"Idempotency-Key": "valid"}).status_code == 409
    app.dependency_overrides[get_learner] = lambda: SimpleNamespace(id="foreign")
    assert client.get(f"/api/v1/sessions/{sid}/next").status_code == 404


def test_unknown_demo_answer_stays_open_and_confidence_not_override(env):
    client, factory, _ = env
    sid = start(env)
    turn = client.get(f"/api/v1/sessions/{sid}/next").json()
    response = client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": turn["item_id"], "answer": "I guess anything", "confidence": 5,
                          "expected_version": turn["version"]}, headers={"Idempotency-Key": "unknown"})
    run_job(factory, response.json()["job_id"])
    feedback = client.get(f"/api/v1/sessions/{sid}/next").json()["feedback"]
    assert feedback["correctness"] == "uncertain" and not feedback["title_complete"]
    assert feedback["guessing_signal"] == "unknown"
    with factory() as db:
        event = db.scalar(select(ProgressEvent))
        assert event.correct is None and calibration([event])["sample_count"] == 0


def test_provider_does_not_silently_fallback_and_rejects_fabricated_quote(monkeypatch):
    monkeypatch.delenv("LEARNING_OS_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    with pytest.raises(ProviderUnavailable):
        OpenAIProvider()
    payload = {"study_locale": "en", "concepts": [{"id": "c", "text": "Grounded."}], "citations": [{"id": "s", "excerpt": "Grounded."}]}
    turn = DemoProvider().generate("turn", payload)
    turn["source_quotes"][0]["quote"] = "Made up."
    with pytest.raises(InvalidModelOutput):
        validate_output("turn", turn, payload)
    payload["study_locale"] = "ar"
    with pytest.raises(ProviderUnavailable):
        DemoProvider().generate("turn", payload)


def test_review_ladder_timezone_and_any_event_replay(env):
    instant = datetime(2026, 10, 13, 23, 30, tzinfo=timezone.utc)
    stage = 0
    for expected_days in [3, 7, 14, 30, 30]:
        stage, due = schedule(stage, True, instant)
        assert due - instant == timedelta(days=expected_days)
    assert schedule(4, False, instant) == (0, instant + timedelta(days=1))
    assert local_due(instant, "Africa/Lagos").startswith("2026-10-14T00:30")
    client, factory, _ = env
    sid = start(env)
    with factory() as db:
        item = db.scalar(select(SessionItem))
        event = ProgressEvent(id="event", learner_id="learner", concept_id=item.concept_id, chunk_id=item.chunk_id,
            session_id=sid, item_id=item.id, confidence=5, correctness="correct", correct=True, answer="synthetic",
            reviewer_json={}, idempotency_key="fixture", timestamp=instant)
        db.add(event); db.flush()
        apply_review(db, event, True, initial=True)
        db.flush()
        state = db.scalar(select(ReviewState))
        due = state.next_review_at
        apply_review(db, event, True)
        assert state.stage == 0 and state.next_review_at == due


def test_coverage_never_uses_confidence_or_hesitation_as_guessing():
    event = SimpleNamespace(id="e", concept_id="c1", timestamp=utcnow(), correct=True, confidence=5,
        correctness="correct", reviewer_json={"guessing_signal": "unsupported", "citation_ids": ["s"]})
    assert not coverage({"c1", "c2"}, [event])["complete"]
    assert coverage({"c1"}, [event])["complete"]
    event.reviewer_json["guessing_signal"] = "unknown"
    assert not coverage({"c1"}, [event])["complete"]


def test_immutable_locale_turn_and_next_turn_selection(env):
    client, factory, _ = env
    sid = start(env)
    turn = client.get(f"/api/v1/sessions/{sid}/next").json()
    with factory() as db:
        learner = db.get(Learner, "learner")
        learner.study_locale = "ar"
        db.commit()
    assert client.get(f"/api/v1/sessions/{sid}/next").json()["generation_locale"] == "en"
    response = client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": turn["item_id"], "answer": "unknown", "confidence": 4,
        "expected_version": turn["version"]}, headers={"Idempotency-Key": "locale"})
    run_job(factory, response.json()["job_id"])
    feedback = client.get(f"/api/v1/sessions/{sid}/next").json()
    assert feedback["feedback"]["correctness"] == "uncertain"
    response = client.post(f"/api/v1/sessions/{sid}/advance", json={"expected_version": feedback["version"]}, headers={"Idempotency-Key": "nextlocale"})
    from app.jobs import NeedsAttention
    with pytest.raises(NeedsAttention):
        run_job(factory, response.json()["job_id"])
    with factory() as db:
        assert db.get(StudySession, sid).scope_revision_id == "scope"
        assert db.query(ProgressEvent).count() == 1


def test_voice_answers_continue_after_three_with_server_assessment(env):
    client, factory, _ = env
    sid = start(env)
    for index in range(3):
        turn = client.get(f"/api/v1/sessions/{sid}/next").json()
        response = client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": turn["item_id"], "answer": "unknown",
            "confidence": 2, "voice": True, "expected_version": turn["version"]}, headers={"Idempotency-Key": f"voice{index}"})
        assert response.status_code == 202
        run_job(factory, response.json()["job_id"])
        run_job(factory, response.json()["job_id"])
        feedback = client.get(f"/api/v1/sessions/{sid}/next").json()
        response = client.post(f"/api/v1/sessions/{sid}/advance", json={"expected_version": feedback["version"]}, headers={"Idempotency-Key": f"vadvance{index}"})
        run_job(factory, response.json()["job_id"])
    turn = client.get(f"/api/v1/sessions/{sid}/next").json()
    payload = {"item_id": turn["item_id"], "answer": "typed", "confidence": 2, "voice": True, "expected_version": turn["version"]}
    response = client.post(f"/api/v1/sessions/{sid}/answer", json=payload, headers={"Idempotency-Key": "fourth"})
    assert response.status_code == 202
    run_job(factory, response.json()["job_id"])
    with factory() as db:
        assert db.query(ProgressEvent).count() == 4
        assert all(e.reviewer_json.get("voice") for e in db.scalars(select(ProgressEvent)))


@pytest.mark.parametrize("locale,answer", [("en", "Recall improves"), ("zh-Hans", "主动回忆"), ("es", "recuperación"),
    ("ar", "الاسترجاع"), ("pt", "recordação"), ("fr", "rappel"), ("ja", "想起"), ("ru", "вспоминание"), ("de", "Abruf"), ("id", "mengingat")])
def test_model_boundary_locale_neutral_assessment(locale, answer, monkeypatch):
    # Mocked transport proves no English keyword gate; it does NOT prove live quality.
    monkeypatch.setenv("LEARNING_OS_API_KEY", "synthetic-not-a-real-key")
    monkeypatch.setenv("LLM_MODEL", "synthetic-model-id")
    provider = OpenAIProvider()
    payload = {"item_id": "item", "confidence": 5, "study_locale": locale, "answer": answer,
        "concepts": [{"id": "concept", "text": "Source idea"}], "citations": [{"id": "cite", "excerpt": "Original source"}],
        "evidence_event_ids": ["event"]}
    verdict = {"item_id": "item", "correctness": "correct", "confidence": 5, "missing_parts": [], "guessing_signal": "unsupported",
        "feedback": answer, "title_complete": True, "rationale": answer, "evidence_event_ids": ["event"], "citation_ids": ["cite"]}
    def request(path, **kwargs):
        import json
        context = json.loads(kwargs["json"]["messages"][1]["content"])
        assert context["study_locale"] == locale and context["answer"] == answer
        assert context["citations"][0]["excerpt"] == "Original source"
        return {"choices": [{"message": {"content": json.dumps(verdict)}}]}
    monkeypatch.setattr(provider, "_request", request)
    assert provider.generate("assessment", payload)["correctness"] == "correct"


def test_retrieval_practice_skill_synthetic_five_question_schema_and_locators():
    import json
    from pathlib import Path
    fixture = json.loads((Path(__file__).parent / "fixtures/retrieval-practice.json").read_text())
    output = validate_output("quiz_set", fixture["quiz"], fixture["context"])
    assert len(output["questions"]) == 5
    assert {"recall", "explain", "apply"} <= {q["kind"] for q in output["questions"]}
    assert {c["id"] for c in fixture["context"]["concepts"]} <= {cid for q in output["questions"] for cid in q["concept_ids"]}
    for question in output["questions"]:
        assert question["expected_answer"].casefold() not in question["question"].casefold()
        for cid in question["citation_ids"]:
            cite = next(c for c in fixture["context"]["citations"] if c["id"] == cid)
            assert cite["excerpt"] and cite["locator"]["line_start"] == cite["locator"]["line_end"]


def test_cold_review_full_coverage_then_thirty_day_cap(env):
    client, factory, _ = env
    with factory() as db:
        db.add(ReviewState(learner_id="learner", chunk_id="chunk", stage=4,
                           next_review_at=utcnow() - timedelta(days=1), needs_attention=False))
        db.commit()
    response = client.post("/api/v1/sessions", json={"collection_id": "collection", "scope_revision_id": "scope", "mode": "review"},
                           headers={"Idempotency-Key": "coldreview"})
    sid = response.json()["id"]
    run_job(factory, response.json()["job_id"])
    for index in range(2):
        turn = client.get(f"/api/v1/sessions/{sid}/next").json()
        assert turn["teaching"] == ""
        with factory() as db:
            answer = db.get(Concept, turn["concept_id"]).text
        response = client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": turn["item_id"], "answer": answer,
            "confidence": 5, "expected_version": turn["version"]}, headers={"Idempotency-Key": f"cold{index}"})
        run_job(factory, response.json()["job_id"])
        feedback = client.get(f"/api/v1/sessions/{sid}/next").json()
        assert feedback["feedback"]["title_complete"] is (index == 1)
        if index == 0:
            response = client.post(f"/api/v1/sessions/{sid}/advance", json={"expected_version": feedback["version"]},
                                   headers={"Idempotency-Key": "coldadvance"})
            run_job(factory, response.json()["job_id"])
    with factory() as db:
        state = db.scalar(select(ReviewState))
        event = db.get(ProgressEvent, state.last_review_event_id)
        assert state.stage == 4 and not state.needs_attention
        from app.db import as_utc
        assert as_utc(state.next_review_at) - as_utc(event.timestamp) == timedelta(days=30)


def test_review_failure_keeps_pinned_title_for_targeted_retry(env, monkeypatch):
    client, factory, _ = env
    with factory() as db:
        db.add(ReviewState(learner_id="learner", chunk_id="chunk", stage=3,
                           next_review_at=utcnow() - timedelta(days=1), needs_attention=False))
        db.commit()
    class IncorrectFixtureProvider(DemoProvider):
        def generate(self, kind, payload):
            verdict = super().generate(kind, payload)
            if kind == "assessment":
                verdict.update(correctness="incorrect", title_complete=False, missing_parts=["Synthetic missed concept"], guessing_signal="unsupported")
            return verdict
    monkeypatch.setattr("app.sessions.get_provider", lambda: IncorrectFixtureProvider())
    response = client.post("/api/v1/sessions", json={"collection_id": "collection", "scope_revision_id": "scope", "mode": "review"},
                           headers={"Idempotency-Key": "failedreview"})
    sid = response.json()["id"]
    run_job(factory, response.json()["job_id"])
    turn = client.get(f"/api/v1/sessions/{sid}/next").json()
    response = client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": turn["item_id"], "answer": "wrong", "confidence": 5,
                           "expected_version": turn["version"]}, headers={"Idempotency-Key": "coldfailure"})
    run_job(factory, response.json()["job_id"])
    feedback = client.get(f"/api/v1/sessions/{sid}/next").json()
    with factory() as db:
        state = db.scalar(select(ReviewState))
        event = db.get(ProgressEvent, state.last_review_event_id)
        assert state.stage == 0 and state.needs_attention
        from app.db import as_utc
        assert as_utc(state.next_review_at) - as_utc(event.timestamp) == timedelta(days=1)
    response = client.post(f"/api/v1/sessions/{sid}/advance", json={"expected_version": feedback["version"]},
                           headers={"Idempotency-Key": "retryweak"})
    run_job(factory, response.json()["job_id"])
    next_turn = client.get(f"/api/v1/sessions/{sid}/next").json()
    assert next_turn["concept_id"] == turn["concept_id"] and next_turn["status"] == "awaiting_answer"
