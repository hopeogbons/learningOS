# Data model, migrations and invariant ownership

UUID primary keys for app entities. Timestamps UTC with timezone awareness. Every learner-owned row contains `learner_id`; parent joins also check matching ownership. Alembic migrations are mandatory from the first backend batch, tested on fresh SQLite and PostgreSQL. Foreign keys and indexes are enforced, not just modeled.

| Entity | Required fields / constraints |
|---|---|
| Learner | OIDC subject+issuer unique, display_name, ui_locale, study_locale, speech_locale, timezone (IANA), consent/preferences; local demo ID separate |
| Collection | learner_id, name, note, icon_key, color_key, drive_folder_id/root ID nullable, storage_mode, folder_mode, provisioning_state/job key, position, version |
| Material | collection_id, learner_id, title, source_type, position, current_revision_id, status |
| MaterialRevision | material_id, hash/provider_revision, drive_file_id, origin, storage_state/receipt, private_blob_key, mime, size, source_url, source_language, extraction_version, created_at; unique owned Collection/source revision |
| Chunk | material_revision_id, learner_id, title, position, source_locator_json; immutable within ingested revision |
| Concept | chunk_id, learner_id, text, citation_ids, critical flag, prompt/model extraction version; immutable extracted content |
| ConceptRelation | collection_id, learner_id, from/to concept, relation type, evidence citation; explicit prerequisite/related relations |
| Citation | revision_id, locator_kind, locator_json, excerpt, excerpt_hash; locator must resolve to extracted source |
| ScopeRevision | collection_id, learner_id, revision_number, active, created_at; one active revision per Collection |
| ScopeItem | scope_revision_id, chunk_id, position; unique title per scope; selection membership frozen |
| StudySession | learner_id, collection_id, scope_revision_id, mode study/review, status, current_item_id, version, started/finished_at |
| SessionItem | session_id, concept_id, question_json_private, public_question, citation_ids, answer_state; generated once per turn |
| ProgressEvent | learner_id, concept/chunk/session/item IDs, timestamp, confidence 1–5, correctness label + nullable correct, answer/transcript private, reviewer_json, idempotency_key unique per learner |
| TitleAssessment | learner_id, chunk_id, scope_revision_id, complete, rationale, evidence_event_ids, critical_coverage; immutable audit records |
| ReviewState | learner_id, chunk_id, stage 0–4, next_review_at, last_review_event_id, needs_attention; unique learner/title revision |
| ProviderConnection | learner_id, provider, encrypted credential reference, scopes, status, folder/checkpoint, last_sync/error; no raw token in plain DB dump |
| Job | learner_id, kind, entity/ref, unique idempotency_key, payload reference, run_at, lease_owner/until, attempts, state/error |
| OutboxEvent | event_id, learner_id, aggregate/version, type, payload reference, processed_at; created with originating transaction |

The old five entities remain recognizable: Collection, Material, Chunk, Concept and ProgressEvent. Additional tables supply missing session state, scope snapshots, source revisions, auth, relationships, review state and reliable background processing. Avoid adding a globally mutable `selected` or `complete` boolean to Chunk as the authoritative per-user status.

## Required calculations and transitions

- Scope: validate all chunk IDs belong to learner+Collection and current source revision; reject duplicates/empty start. Replace the active scope in one transaction with optimistic version checking. Sessions bind to their scope snapshot and continue if a later scope is created. Removing/deleting referenced material requires confirmation/archive behavior and clear affected-scope UI.
- Ordering: accept a complete list of sibling IDs and expected parent version; validate set equality, parent/tenant, uniqueness. Persist contiguous positions in a transaction. Conflicting reorder returns 409 and refresh guidance.
- Session next: read-only client operation returns a persisted current item; generation job initiated at session creation or `POST .../advance`. Repeated GET cannot consume another turn or bill for new generation. Answer endpoint uses idempotency key + expected version; event, completion decision, review initialization and outbox are atomic.
- Completion: server guards Reviewer verdict using coverage evidence for critical concepts, scope membership and valid citations. Human-correctable error reporting exists; title assessment rationale visible. A broad title needs adequate coverage, not one answer.
- Review: initial completion sets stage 0, due +1 day. On success stage=min(stage+1,4), next due=attempt instant+[1,3,7,14,30][stage] days. On failure stage=0, next due=attempt instant+1 day. Replayed event cannot advance twice. Historic completion remains available separately.
- Weak spots: derive from cited failed/uncertain attempts and review state within a scope/Collection, with timestamps; no unrestricted cross-Collection memory leakage. Calibration views only compare identical attempt windows and display sample count.

## Indexes and retention

Index `(learner_id, collection_id, position)`, scope membership, `(learner_id, next_review_at)`, jobs `(state, run_at, lease_until)`, citation revision and progress history `(learner_id, chunk_id, timestamp)`. Paginate histories/outline/material lists; cursor defaults 50, cap 200. Query-count regression checks avoid per-row source joins. Soft-delete/archive linked sources until retention expiry; learner deletion revokes OAuth, removes blobs and learner-owned rows/jobs with an auditable non-content receipt. Export includes their data only.

## Revision 2 durable state additions

ProviderConnection persists app-root ID and scope capabilities after actual verification. DriveProvisioning/SourceWriteReceipt entity (or equivalent unique durable job/receipt fields) stores owner/Collection, stable identity, destination folder ID, upload idempotency/origin, remote file/revision, stage and last checked time. Validate uniqueness for each provisioning identity and upload transaction. Recover external success after failed DB commit before creating another resource; provider/file identity is not deduplicated globally across unrelated learners. Link receipt stores immutable permitted URL snapshot/locators, schema version and source type; manually edited managed descriptors are revalidated, never executed.

Sessions and ProgressEvent persist generation/answer locales and provider/prompt version for reproducible cross-language grading; display preference does not alter source IDs, progress denominator or review due time. Keep prior `locale` as a migration alias only if implementing on earlier code; this empty-project build starts with explicit fields. Add catalog/source/speech capability metadata separate from assertions of actual support.

## Source chunk preparation update (2026-10-14)

New local PDF/text/Markdown extraction uses `source-excerpts-v2`. Retrieval units stay within their original page or heading and are capped at 4,000 characters, preferring paragraph, sentence, then whitespace boundaries; unbroken text uses an exact bounded slice. PDF first-line titles are deterministic labels, not a semantic topic-classifier claim. Split locators retain the original page/heading and `section_char_start`/`section_char_end`; text line ranges account for leading blank lines. CSV/XLSX row/sheet/cell handling is preserved. Old material revisions, scopes, citations and completion history are not silently re-extracted. Original bytes remain privately retained and owner-authorized citation downloads return the original, not a chunk substitute. Preparation/indexing precedes Study teaching and assessment; no fine-tuning or measured latency claim is implied.
