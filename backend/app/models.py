"""Durable UUID/tenant model. Mutable progress never lives on source Chunk rows."""
from uuid import uuid4
from sqlalchemy import String, Text, Integer, Boolean, DateTime, Float, JSON, ForeignKey, UniqueConstraint, Index, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .db import Base, utcnow

def uuidstr():
    return str(uuid4())

class Entity:
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuidstr)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)

class Owned(Entity):
    learner_id: Mapped[str] = mapped_column(ForeignKey("learners.id", ondelete="CASCADE"), index=True)

class Learner(Entity, Base):
    __tablename__ = "learners"
    oidc_subject: Mapped[str | None] = mapped_column(String(255))
    oidc_issuer: Mapped[str | None] = mapped_column(String(2048))
    display_name: Mapped[str] = mapped_column(String(120), default="Demo Learner")
    ui_locale: Mapped[str] = mapped_column(String(20), default="en")
    study_locale: Mapped[str] = mapped_column(String(20), default="en")
    speech_locale: Mapped[str] = mapped_column(String(20), default="en-GB")
    timezone: Mapped[str] = mapped_column(String(100), default="Africa/Lagos")
    preferences: Mapped[dict] = mapped_column(JSON, default=dict)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("oidc_subject", "oidc_issuer"),)

class AuthSession(Owned, Base):
    __tablename__ = "auth_sessions"
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    csrf_hash: Mapped[str] = mapped_column(String(64))
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)

class Collection(Owned, Base):
    __tablename__ = "collections"
    name: Mapped[str] = mapped_column(String(200))
    note: Mapped[str] = mapped_column(Text, default="")
    icon_key: Mapped[str] = mapped_column(String(50), default="book")
    color_key: Mapped[str] = mapped_column(String(50), default="blue")
    drive_folder_id: Mapped[str | None] = mapped_column(String(255))
    drive_root_id: Mapped[str | None] = mapped_column(String(255))
    storage_mode: Mapped[str] = mapped_column(String(20), default="local")
    folder_mode: Mapped[str] = mapped_column(String(30), default="app-managed")
    provisioning_state: Mapped[str] = mapped_column(String(30), default="local-only")
    provisioning_job_id: Mapped[str | None] = mapped_column(String(36))
    position: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    last_sync: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (Index("ix_collection_order", "learner_id", "position"),)

class Material(Owned, Base):
    __tablename__ = "materials"
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    source_type: Mapped[str] = mapped_column(String(40), default="text")
    position: Mapped[int] = mapped_column(Integer, default=0)
    current_revision_id: Mapped[str | None] = mapped_column(ForeignKey("material_revisions.id", name="fk_material_current_revision", ondelete="SET NULL", use_alter=True))
    status: Mapped[str] = mapped_column(String(30), default="queued")
    archived: Mapped[bool] = mapped_column(Boolean, default=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    deletion_job_id: Mapped[str | None] = mapped_column(String(36))
    __table_args__ = (Index("ix_material_order", "learner_id", "collection_id", "position"),)

class MaterialRevision(Owned, Base):
    __tablename__ = "material_revisions"
    material_id: Mapped[str] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"), index=True)
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    content_hash: Mapped[str] = mapped_column(String(64))
    provider_revision: Mapped[str | None] = mapped_column(String(255))
    drive_file_id: Mapped[str | None] = mapped_column(String(255))
    origin: Mapped[str] = mapped_column(String(30), default="ui_upload")
    storage_state: Mapped[str] = mapped_column(String(30), default="local-only")
    storage_receipt: Mapped[dict] = mapped_column(JSON, default=dict)
    private_blob_key: Mapped[str | None] = mapped_column(String(1000))
    mime: Mapped[str] = mapped_column(String(150), default="text/plain")
    size: Mapped[int] = mapped_column(Integer, default=0)
    source_url: Mapped[str | None] = mapped_column(Text)
    source_language: Mapped[str] = mapped_column(String(30), default="und")
    extraction_version: Mapped[str] = mapped_column(String(100), default="v1")
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("learner_id", "collection_id", "drive_file_id", "provider_revision", name="uq_owned_remote_revision"), CheckConstraint("size >= 0", name="ck_revision_size"))

class Chunk(Owned, Base):
    __tablename__ = "chunks"
    material_revision_id: Mapped[str] = mapped_column(ForeignKey("material_revisions.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    position: Mapped[int] = mapped_column(Integer, default=0)
    source_locator_json: Mapped[dict] = mapped_column(JSON, default=dict)
    text: Mapped[str] = mapped_column(Text, default="")

class Concept(Owned, Base):
    __tablename__ = "concepts"
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), index=True)
    text: Mapped[str] = mapped_column(Text)
    citation_ids: Mapped[list] = mapped_column(JSON, default=list)
    critical: Mapped[bool] = mapped_column(Boolean, default=True)
    extraction_version: Mapped[str] = mapped_column(String(100), default="v1")
    position: Mapped[int] = mapped_column(Integer, default=0)

class Citation(Owned, Base):
    __tablename__ = "citations"
    revision_id: Mapped[str] = mapped_column(ForeignKey("material_revisions.id", ondelete="CASCADE"), index=True)
    locator_kind: Mapped[str] = mapped_column(String(30))
    locator_json: Mapped[dict] = mapped_column(JSON)
    excerpt: Mapped[str] = mapped_column(Text)
    excerpt_hash: Mapped[str] = mapped_column(String(64))

class ConceptRelation(Owned, Base):
    __tablename__ = "concept_relations"
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    from_concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    to_concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    relation_type: Mapped[str] = mapped_column(String(50))
    evidence_citation_id: Mapped[str] = mapped_column(ForeignKey("citations.id", ondelete="CASCADE"))

class ScopeRevision(Owned, Base):
    __tablename__ = "scope_revisions"
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    revision_number: Mapped[int] = mapped_column(Integer)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("collection_id", "revision_number"), Index("uq_active_scope", "collection_id", unique=True, sqlite_where=__import__("sqlalchemy").text("active = 1"), postgresql_where=__import__("sqlalchemy").text("active")))

class ScopeItem(Owned, Base):
    __tablename__ = "scope_items"
    scope_revision_id: Mapped[str] = mapped_column(ForeignKey("scope_revisions.id", ondelete="CASCADE"), index=True)
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"))
    position: Mapped[int] = mapped_column(Integer)
    __table_args__ = (UniqueConstraint("scope_revision_id", "chunk_id"),)

class StudySession(Owned, Base):
    __tablename__ = "study_sessions"
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"), index=True)
    scope_revision_id: Mapped[str] = mapped_column(ForeignKey("scope_revisions.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(20), default="study")
    status: Mapped[str] = mapped_column(String(30), default="generating")
    current_item_id: Mapped[str | None] = mapped_column(ForeignKey("session_items.id", name="fk_session_current_item", ondelete="SET NULL", use_alter=True))
    version: Mapped[int] = mapped_column(Integer, default=1)
    started_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    generation_locale: Mapped[str] = mapped_column(String(20), default="en")
    summary_json: Mapped[dict] = mapped_column(JSON, default=dict)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)

class SessionItem(Owned, Base):
    __tablename__ = "session_items"
    session_id: Mapped[str] = mapped_column(ForeignKey("study_sessions.id", ondelete="CASCADE"), index=True)
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"))
    question_json_private: Mapped[dict] = mapped_column(JSON, default=dict)
    public_question: Mapped[str] = mapped_column(Text, default="")
    teaching: Mapped[str] = mapped_column(Text, default="")
    citation_ids: Mapped[list] = mapped_column(JSON, default=list)
    answer_state: Mapped[str] = mapped_column(String(30), default="pending")
    position: Mapped[int] = mapped_column(Integer, default=0)
    generation_locale: Mapped[str] = mapped_column(String(20), default="en")
    provider_version: Mapped[str] = mapped_column(String(100), default="fake-v1")
    feedback_json: Mapped[dict] = mapped_column(JSON, default=dict)

class ProgressEvent(Owned, Base):
    __tablename__ = "progress_events"
    concept_id: Mapped[str] = mapped_column(ForeignKey("concepts.id", ondelete="CASCADE"))
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"), index=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("study_sessions.id", ondelete="CASCADE"))
    item_id: Mapped[str] = mapped_column(ForeignKey("session_items.id", ondelete="CASCADE"))
    timestamp: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    confidence: Mapped[int] = mapped_column(Integer)
    correctness: Mapped[str] = mapped_column(String(30), default="uncertain")
    correct: Mapped[bool | None] = mapped_column(Boolean)
    answer: Mapped[str] = mapped_column(Text)
    reviewer_json: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(255))
    answer_locale: Mapped[str] = mapped_column(String(20), default="en")
    provider_version: Mapped[str] = mapped_column(String(100), default="fake-v1")
    __table_args__ = (UniqueConstraint("learner_id", "idempotency_key"), Index("ix_history", "learner_id", "chunk_id", "timestamp"), CheckConstraint("confidence BETWEEN 1 AND 5", name="ck_confidence_range"))

class TitleAssessment(Owned, Base):
    __tablename__ = "title_assessments"
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"))
    scope_revision_id: Mapped[str] = mapped_column(ForeignKey("scope_revisions.id", ondelete="CASCADE"), index=True)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)
    rationale: Mapped[str] = mapped_column(Text, default="")
    evidence_event_ids: Mapped[list] = mapped_column(JSON, default=list)
    critical_coverage: Mapped[dict] = mapped_column(JSON, default=dict)

class ReviewState(Owned, Base):
    __tablename__ = "review_states"
    chunk_id: Mapped[str] = mapped_column(ForeignKey("chunks.id", ondelete="CASCADE"))
    stage: Mapped[int] = mapped_column(Integer, default=0)
    next_review_at: Mapped[object] = mapped_column(DateTime(timezone=True), index=True)
    last_review_event_id: Mapped[str | None] = mapped_column(String(36))
    needs_attention: Mapped[bool] = mapped_column(Boolean, default=False)
    __table_args__ = (UniqueConstraint("learner_id", "chunk_id"), Index("ix_owned_due", "learner_id", "next_review_at"), CheckConstraint("stage BETWEEN 0 AND 4", name="ck_review_stage"))

class ProviderConnection(Owned, Base):
    __tablename__ = "provider_connections"
    provider: Mapped[str] = mapped_column(String(40))
    encrypted_credentials: Mapped[str | None] = mapped_column(Text)
    scopes: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(30), default="disconnected")
    app_root_id: Mapped[str | None] = mapped_column(String(255))
    checkpoint: Mapped[dict] = mapped_column(JSON, default=dict)
    capability_json: Mapped[dict] = mapped_column(JSON, default=dict)
    last_sync: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(100))
    __table_args__ = (UniqueConstraint("learner_id", "provider"),)

class SourceWriteReceipt(Owned, Base):
    __tablename__ = "source_write_receipts"
    collection_id: Mapped[str] = mapped_column(ForeignKey("collections.id", ondelete="CASCADE"))
    material_id: Mapped[str | None] = mapped_column(ForeignKey("materials.id", ondelete="CASCADE"))
    stable_identity: Mapped[str] = mapped_column(String(255))
    folder_id: Mapped[str | None] = mapped_column(String(255))
    origin: Mapped[str] = mapped_column(String(30))
    drive_file_id: Mapped[str | None] = mapped_column(String(255))
    provider_revision: Mapped[str | None] = mapped_column(String(255))
    stage: Mapped[str] = mapped_column(String(30), default="queued")
    checked_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    receipt_json: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__ = (UniqueConstraint("learner_id", "collection_id", "stable_identity"),)

class Job(Owned, Base):
    __tablename__ = "jobs"
    kind: Mapped[str] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(36))
    idempotency_key: Mapped[str | None] = mapped_column(String(255))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[dict] = mapped_column(JSON, default=dict)
    run_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    lease_owner: Mapped[str | None] = mapped_column(String(100))
    lease_until: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[str] = mapped_column(String(30), default="queued")
    progress: Mapped[int] = mapped_column(Integer, default=0)
    error_code: Mapped[str | None] = mapped_column(String(100))
    retryable: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("learner_id", "idempotency_key"), Index("ix_job_claim", "state", "run_at", "lease_until"))

class OutboxEvent(Owned, Base):
    __tablename__ = "outbox_events"
    aggregate_id: Mapped[str] = mapped_column(String(36))
    aggregate_version: Mapped[int] = mapped_column(Integer)
    event_type: Mapped[str] = mapped_column(String(80))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    processed_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    __table_args__ = (UniqueConstraint("aggregate_id", "aggregate_version", "event_type"),)

class Notification(Owned, Base):
    __tablename__ = "notifications"
    kind: Mapped[str] = mapped_column(String(50))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text, default="")
    entity_id: Mapped[str | None] = mapped_column(String(36))
    read_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))

class WorkerHeartbeat(Entity, Base):
    __tablename__ = "worker_heartbeats"
    worker_id: Mapped[str] = mapped_column(String(100), unique=True)
    checked_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
