"""Coverage-aware completion and replay-safe review scheduling."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from .db import as_utc, utcnow
from .models import ReviewState

INTERVALS = (1, 3, 7, 14, 30)


def schedule(stage: int, success: bool, at: datetime) -> tuple[int, datetime]:
    stage = min(max(stage + 1, 0), 4) if success else 0
    return stage, as_utc(at) + timedelta(days=INTERVALS[stage])


def local_due(at: datetime, timezone: str) -> str:
    return as_utc(at).astimezone(ZoneInfo(timezone)).isoformat()


def calibration(events) -> dict:
    matched = [e for e in events if e.correct is not None and e.correctness != "uncertain"]
    count = len(matched)
    if not count:
        return {"sample_count": 0, "mean_confidence": None, "accuracy": None, "gap": None, "brier_score": None}
    confidence = sum((e.confidence - 1) / 4 for e in matched) / count
    accuracy = sum(bool(e.correct) for e in matched) / count
    brier = sum(((e.confidence - 1) / 4 - int(bool(e.correct))) ** 2 for e in matched) / count
    return {"sample_count": count, "mean_confidence": confidence, "accuracy": accuracy, "gap": confidence - accuracy, "brier_score": brier}


def coverage(critical_ids: set[str], events) -> dict:
    # Latest evidence decides each concept; wrong/uncertain evidence supersedes prior success.
    latest = {}
    for event in sorted(events, key=lambda e: (as_utc(e.timestamp), e.id)):
        latest[event.concept_id] = event
    supported = {cid: e for cid, e in latest.items() if e.correct is True and e.confidence >= 4
                 and e.reviewer_json.get("guessing_signal") == "unsupported" and e.reviewer_json.get("citation_ids")}
    demonstrated = set(supported) & critical_ids
    return {"critical_ids": sorted(critical_ids), "demonstrated_ids": sorted(demonstrated),
            "complete": bool(critical_ids) and critical_ids <= demonstrated,
            "evidence_event_ids": [supported[cid].id for cid in sorted(demonstrated)]}


def apply_review(db, event, success: bool, initial: bool = False):
    """Event marker prevents a replay of *any* historic event advancing again."""
    if event.reviewer_json.get("review_applied"):
        return
    state = db.scalar(select(ReviewState).where(ReviewState.learner_id == event.learner_id,
                                               ReviewState.chunk_id == event.chunk_id).with_for_update())
    at = as_utc(event.timestamp)
    if state is None:
        state = ReviewState(learner_id=event.learner_id, chunk_id=event.chunk_id, stage=0,
                            next_review_at=at + timedelta(days=1), needs_attention=not success)
        db.add(state)
    elif not initial:
        state.stage, state.next_review_at = schedule(state.stage, success, at)
        state.needs_attention = not success
    state.last_review_event_id = event.id
    event.reviewer_json = {**event.reviewer_json, "review_applied": True, "review_success": success}
