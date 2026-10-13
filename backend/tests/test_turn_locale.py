"""Synthetic two-turn locale regression; no live multilingual quality claim."""
import copy
import importlib.util
from pathlib import Path
from sqlalchemy import select

spec = importlib.util.spec_from_file_location("learning_test_fixture", Path(__file__).with_name("test_learning.py"))
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
env = fixture.env


def test_next_turn_snapshots_current_profile_without_mutating_pending_turn(env, monkeypatch):
    from app.core_api import router as core_router
    from app.models import SessionItem, ProgressEvent, StudySession, Citation
    from app.llm import DemoProvider

    calls = []
    class RecordingFakeProvider:
        name = "synthetic-recording-only"
        version = "synthetic-locale-contract-v1"
        def generate(self, kind, context):
            calls.append((kind, copy.deepcopy(context)))
            # This fixture deliberately performs no translation and tests propagation only.
            normalized = {**context, "study_locale": "en"}
            return DemoProvider().generate(kind, normalized)

    monkeypatch.setattr("app.sessions.get_provider", lambda: RecordingFakeProvider())
    client, factory, app = env
    app.include_router(core_router, prefix="/api/v1")
    from fastapi import Depends
    from app.db import get_db
    from app.auth import get_learner
    from app.models import Learner
    def principal(db=Depends(get_db)):
        return db.get(Learner, "learner")
    app.dependency_overrides[get_learner] = principal
    sid = fixture.start(env)
    initial = client.get(f"/api/v1/sessions/{sid}/next").json()
    assert initial["generation_locale"] == "en"
    with factory() as db:
        initial_private = copy.deepcopy(db.get(SessionItem, initial["item_id"]).question_json_private)
        original_citations = {c.id: (c.excerpt, c.excerpt_hash, c.locator_json) for c in db.scalars(select(Citation))}

    update = client.patch("/api/v1/me", json={"study_locale": "fr"})
    assert update.status_code == 200, update.text
    assert update.json()["study_locale"] == "fr"
    assert client.get(f"/api/v1/sessions/{sid}/next").json() == initial
    with factory() as db:
        item = db.get(SessionItem, initial["item_id"])
        assert item.question_json_private == initial_private
        assert item.generation_locale == "en" and item.answer_state == "pending"
        assert db.get(StudySession, sid).scope_revision_id == "scope"
        assert db.query(ProgressEvent).count() == 0

    answer = client.post(f"/api/v1/sessions/{sid}/answer", json={"item_id": initial["item_id"],
        "answer": "synthetic unknown response", "confidence": 4, "expected_version": initial["version"]},
        headers={"Idempotency-Key": "recording-locale-answer"})
    assert answer.status_code == 202
    fixture.run_job(factory, answer.json()["job_id"])
    feedback = client.get(f"/api/v1/sessions/{sid}/next").json()
    assert feedback["generation_locale"] == "en"
    advance = client.post(f"/api/v1/sessions/{sid}/advance", json={"expected_version": feedback["version"]},
        headers={"Idempotency-Key": "recording-locale-advance"})
    assert advance.status_code == 202
    fixture.run_job(factory, advance.json()["job_id"])
    next_turn = client.get(f"/api/v1/sessions/{sid}/next").json()
    assert next_turn["generation_locale"] == "fr" and next_turn["item_id"] != initial["item_id"]
    assert next_turn["citation_ids"] == initial["citation_ids"]
    assert [context["study_locale"] for kind, context in calls] == ["en", "en", "fr"]
    assert calls[0][1]["citations"] == calls[-1][1]["citations"]
    with factory() as db:
        first = db.get(SessionItem, initial["item_id"])
        second = db.get(SessionItem, next_turn["item_id"])
        assert first.question_json_private == initial_private
        assert first.generation_locale == "en" and second.generation_locale == "fr"
        assert db.get(StudySession, sid).scope_revision_id == "scope"
        event = db.scalar(select(ProgressEvent))
        assert db.query(ProgressEvent).count() == 1 and event.answer_locale == "en"
        assert original_citations == {c.id: (c.excerpt, c.excerpt_hash, c.locator_json) for c in db.scalars(select(Citation))}
