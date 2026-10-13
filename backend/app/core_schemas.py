"""Public response contracts: safe DTOs, never ORM/private credentials or rubrics."""
from typing import Literal
from pydantic import BaseModel, Field

class LearnerDTO(BaseModel):
    id: str
    display_name: str
    ui_locale: str
    study_locale: str
    speech_locale: str
    timezone: str
    is_demo: bool
    mode: str

class ScopeDTO(BaseModel):
    id: str
    revision_number: int
    created_at: str
    chunk_ids: list[str]

class ProgressDTO(BaseModel):
    scope_revision_id: str | None
    completed_count: int
    total_in_scope: int
    percent: int
    review_needed_count: int

class CollectionDTO(BaseModel):
    id: str
    name: str
    note: str
    icon_key: str
    color_key: str
    storage_mode: str
    folder_mode: str
    provisioning_state: str
    drive_folder_id: str | None
    position: int
    version: int
    archived: bool
    created_at: str
    last_sync: str | None
    last_sync_at: str | None
    material_count: int
    active_scope: ScopeDTO | None
    progress: ProgressDTO

class CollectionListDTO(BaseModel):
    items: list[CollectionDTO]
    total: int
    next_cursor: int | None

class MaterialDTO(BaseModel):
    id: str
    collection_id: str
    title: str
    source_type: str
    position: int
    version: int
    status: str
    current_revision_id: str | None
    created_at: str
    origin: str | None
    source_language: str
    storage_state: str
    size: int

class MaterialListDTO(BaseModel):
    items: list[MaterialDTO]
    total: int
    next_cursor: int | None

class ChunkDTO(BaseModel):
    id: str
    title: str
    position: int
    citation_ids: list[str]
    selected: bool

class OutlineMaterialDTO(MaterialDTO):
    chunks: list[ChunkDTO]

class OutlineDTO(BaseModel):
    materials: list[OutlineMaterialDTO]
    active_scope: ScopeDTO | None
    version: int
    progress: ProgressDTO

class ScopeResultDTO(BaseModel):
    scope_revision: ScopeDTO
    progress: ProgressDTO
    version: int

class OrderResultDTO(BaseModel):
    ordered_ids: list[str]
    version: int

class ArchiveResultDTO(BaseModel):
    id: str
    state: Literal["archived"]
    version: int

class CalibrationDTO(BaseModel):
    sample_count: int
    confidence: float
    accuracy: float
    gap: float
    brier_score: float | None
    window: str

class ResumeDTO(BaseModel):
    session_id: str
    collection_id: str
    scope_revision_id: str
    status: str
    title: str

class ConnectionSummaryDTO(BaseModel):
    provider: str
    status: str

class CollectionProgressDTO(ProgressDTO):
    collection_id: str

class DashboardDTO(BaseModel):
    learner: LearnerDTO
    collections_count: int
    due_count: int
    collections: list[CollectionDTO]
    scope_progress: list[CollectionProgressDTO]
    resume: ResumeDTO | None
    calibration: CalibrationDTO
    recent_materials: list[MaterialDTO]
    connections: list[ConnectionSummaryDTO]
    mode: str
    demo_notice: str | None

class JobDTO(BaseModel):
    id: str
    job_id: str
    kind: str
    status: str
    state: str
    progress: int
    attempts: int
    retryable: bool
    error_code: str | None
    # Handler results contain public IDs/status only; schemas for those are routed elsewhere.
    result: dict[str, object]
    created_at: str

class SearchItemDTO(BaseModel):
    id: str
    type: Literal["material", "chunk", "concept", "citation"]
    title: str
    collection_id: str

class SearchDTO(BaseModel):
    items: list[SearchItemDTO]
    total: int
    next_cursor: int | None

class NotificationDTO(BaseModel):
    id: str
    kind: str
    title: str
    body: str
    entity_id: str | None
    read_at: str | None
    created_at: str

class NotificationListDTO(BaseModel):
    items: list[NotificationDTO]
    total: int
    next_cursor: int | None

class NoticeReadDTO(BaseModel):
    id: str
    read_at: str

class CitationDTO(BaseModel):
    id: str
    excerpt: str
    locator_kind: str
    locator: dict[str, object]
    revision_id: str
    material_id: str
    source_title: str
    source_language: str
    source_url: str | None
    viewer_url: str | None

class LanguageStatusDTO(BaseModel):
    status: str

class LanguageDTO(BaseModel):
    locale: str
    native_label: str
    english_label: str
    direction: Literal["ltr", "rtl"]
    ui: LanguageStatusDTO
    study: LanguageStatusDTO
    stt: LanguageStatusDTO
    tts: LanguageStatusDTO
    speech_variants: list[str]

class LanguageListDTO(BaseModel):
    items: list[LanguageDTO]

class DeleteQueuedDTO(BaseModel):
    job_id: str
    state: str

class HistoryItemDTO(BaseModel):
    id: str
    chunk_id: str
    concept_id: str
    timestamp: str
    confidence: int
    correct: bool | None
    correctness: str
    reviewer: dict[str, object]

class HistoryDTO(BaseModel):
    items: list[HistoryItemDTO]
    total: int
    next_cursor: int | None
    calibration: CalibrationDTO

class WeakSpotDTO(BaseModel):
    chunk_id: str
    title: str
    concept_id: str
    concept: str
    citation_ids: list[str]
    timestamp: str
    next_review_at: str | None

class WeakSpotsDTO(BaseModel):
    items: list[WeakSpotDTO]
    total: int
    scope_revision_id: str | None

class ErrorDetailDTO(BaseModel):
    code: str
    message: str
    retryable: bool
    request_id: str | None
    details: dict[str, object]

class ErrorEnvelopeDTO(BaseModel):
    error: ErrorDetailDTO

class HealthDTO(BaseModel):
    status: Literal["ok"]
    mode: str
    version: str

class ReadinessDTO(BaseModel):
    status: Literal["ready", "not-ready"]
    mode: str
    dependencies: dict[str, str]
