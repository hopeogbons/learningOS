# API contract — version 1

All backend routes begin `/api/v1`. UUIDs and RFC3339 UTC timestamps; locale-independent field names; text in UTF-8. Backend Pydantic schemas generate authoritative OpenAPI at `/openapi.json`. Generate frontend DTOs from that document and add a CI drift check. This table is the implementation contract; it is not a claim that endpoints already exist.

Authentication is per-learner except health and OIDC start/callback. Envelope errors `{error:{code,message,retryable,request_id,details}}` with no provider secret. Standard 400/401/403/404/409/413/422/429/503. Inaccessible tenant IDs return indistinguishable 404. Limit pagination to 50 default/200 cap.

| Method / route | Input / behavior | Output |
|---|---|---|
| GET `/health` | liveness, no dependency secrets | `{status:"ok",mode,version}` |
| GET `/ready` | database/migration/worker freshness/required providers | ready or 503 with sanitized dependencies |
| GET `/auth/login`, GET `/auth/callback` | OIDC/PKCE/state/nonce | redirect + opaque secure session |
| POST `/auth/logout` | CSRF protected | session revoked |
| GET `/me`, PATCH `/me` | display_name, ui_locale, study_locale, speech_locale, timezone; reject unsupported tags | persisted learner profile |
| GET `/me/export`, DELETE `/me` | authenticated; delete requires explicit confirmation token | private export / deletion job |
| GET `/dashboard` | one consistent authenticated snapshot | learner, collections_count, due_count, scope_progress, resume, calibration, recent_materials, connection summary |
| GET `/collections`, POST `/collections` | name, note, icon/color key, storage_mode local/drive (Drive default when connected); cursor | Collection + folder provisioning state/job; no fake ready folder |
| GET/PATCH/DELETE `/collections/{id}` | ownership/version; archive policy | Collection / outcome |
| POST `/collections/{id}/materials` | multipart PDF/Markdown/text/DOCX/RST/CSV/TSV/XLSX/JSON/YAML/log/JPG/PNG; persisted parent-folder routing; per-source limits; idempotency; managed Drive upload when connected | 202 `{job_id,material_id,state,storage_state}`; final provider receipt proves saved |
| GET `/collections/{id}/materials` | paginated metadata | materials+revision status |
| GET `/ingestion/limits` | authenticated; reports effective upload cap after installation configuration | `{max_upload_bytes}` |
| GET `/materials/{id}/ingestion-pages` | owner; cursor and limit 1–40; current revision only | completeness manifest with global page numbers, extraction method, status, warning and page text excerpt capped at 200,000 characters |
| PATCH `/materials/{id}/ingestion-pages/{page}` | owner; `{text,expected_version}`; only review-required page of an unfinished PDF revision | page correction recorded; next batch/finalize job status |
| DELETE `/collections/{id}/materials/{material_id}` | owner + parent Collection; `{expected_version,confirmation:"DELETE"}`; idempotent durable deletion job | 202 JobDTO; completion only after Drive file deletion and private-object cleanup are confirmed |
| GET `/collections/{id}/outline` | scope revision and material ordering | materials[{id,title,chunks[{id,title,citation_ids,selected,position}]}], active_scope, version |
| POST `/collections/{id}/scope` | `{chunk_ids,expected_version}` | immutable scope_revision + progress |
| PATCH `/collections/{id}/materials/reorder` | `{ordered_ids,expected_version}` | new version and ordering |
| PATCH `/collections/{id}/materials/{material_id}/chunks/reorder` | same; complete siblings only | persisted order/version |
| GET `/collections/{id}/progress` | optional scope_revision_id | completed_count,total_in_scope,percent, review_needed_count |
| GET `/collections/{id}/history` | matched time window/cursor | attempts/calibration/sample_count |
| GET `/collections/{id}/weak-spots` | scope/window | cited weak concepts and next due |
| POST `/sessions` | `{collection_id,scope_revision_id,mode}`; mode study/review | 202 session + first generation job |
| GET `/sessions/{id}` | persisted state | session/status/current turn |
| GET `/sessions/{id}/next` | no side effects; pending=202 | teaching,citations,question,item_id,version; **no expected_answer/rubric** |
| POST `/sessions/{id}/answer` | `{item_id,answer,confidence,expected_version}`; Idempotency-Key | 202 review job; subsequent state has feedback/verdict |
| POST `/sessions/{id}/advance` | acknowledged feedback/expected_version | 202 next-item job; repeat idempotently |
| POST `/sessions/{id}/finish` | explicit learner finish; idempotent | summary job/status; only successfully assessed work counts |
| GET `/sessions/{id}/summary` | privacy protected | covered titles, matched calibration, completed/remaining, citations |
| GET `/review/due` | optional collection; server clock (demo/test clock injected only) | due titles,next_review_at,stage,needs_attention |
| GET `/material-revisions/{revision_id}/original` | ownership checked; immutable retained original bytes | private no-store original download, never chunk-only replacement |
| GET `/citations/{id}` | ownership; revision locator resolves | excerpt,source metadata,authorized viewer URL/coordinates |
| GET `/jobs/{id}` | owner only | status/progress/retryable/error_code/result IDs |
| POST `/jobs/{id}/retry` | idempotent; failed/needs-attention only | queued job outcome |
| GET `/jobs/{id}` | deletion/extraction job owner only; bounded result | state and sanitized page/batch progress |
| GET `/connections` | actual status + supported runtime providers | capability rows |
| POST `/connections/{provider}/connect` | explicit consent; scoped Drive read/create/upload, Gmail read-only | OAuth start URL with disclosed scopes |
| GET `/connections/{provider}/callback` | session-bound state validation | connected redirect |
| DELETE `/connections/{provider}` | revoke/disconnect/remove credential | outcome |
| POST `/collections/{id}/drive-folder` | folder id validated via user's adapter | linked Collection |
| POST `/collections/{id}/sync` | actual source adapter; dedup/revision checkpoint | 202 sync job |
| POST `/collections/{id}/link` | `{url}`; safe public page/captions; managed descriptor/snapshot into owned folder | 202 job + storage state or clear unsupported/no-captions |
| GET `/search` | q, collection filter, cursor | owned titles/concepts/materials/citations only |
| GET `/notifications`, POST `/notifications/{id}/read` | in-app due/job notices; no email sending | owned notices/outcome |

Confidence is required before feedback and cannot be changed after seeing the verdict. Duplicate submissions return the prior job/result with no second ProgressEvent, completion or review-stage increment. Finish is explicit at end of study flow and also processed on natural completion; abandoning a tab does not falsely complete learning. Durable outbox ensures the end-summary runs once per session version.

## Dashboard DTO design

Backend returns serializable JSON only: semantic icon keys and color keys, numeric progress and counts, status/route IDs, bounded row subsets plus total counts. Frontend maps these to original Lucide components and palette. `due_count` and displayed preview length may differ deliberately; label counts from the same snapshot. All Home links pass collection/scope IDs when needed. Confidence and accuracy use the same window/sample count. Greetings use learner local time, never a hardcoded 'Good Morning'.

Voice Study is a two-way conversation over the same session state machine: tutor messages (cited teaching, question, Reviewer feedback) may be spoken; learner speech becomes an editable transcript and then uses the same confidence/answer/grading endpoint as typed text. Server speech endpoints provide verified selected-language STT/TTS when browser support is absent, with explicit permission/privacy/quotas and session ownership. They are required to meet the all-ten spoken target if a browser cannot do so; typing is still available on permission denial or outage. Live date-override query parameters are forbidden; time travel lives in demo CLI/test clock only.

## Revision 2 API additions

| Method / route | Input / behavior | Output |
|---|---|---|
| GET `/languages` | declared catalogs and real provider/browser-independent capability status | locale/native/English label/direction; separate ui/study/stt/tts verification, speech variants |
| POST `/collections/{id}/drive-folder/provision` | owned connection; expected Collection version; idempotency | 202 reconciliation/provision job; persisted root/folder IDs on ready |
| GET `/collections/{id}/storage-status` | ownership | folder mode/provision state, last_sync, queued writes, sanitized errors |
| GET `/materials/{id}/storage-status` | owner and actual provider receipt | origin, state, drive_file_id/provider_revision only when bound, retry/result |
| POST `/sessions/{id}/speech/transcribe` | current owned item; multipart transient audio + supported speech_locale; duration/byte/CSRF checks | transcript preview + detected/requested language; no grading before confirmed answer |
| POST `/sessions/{id}/speech/synthesize` | owned public message/turn ID + supported speech_locale; no hidden answer content | ephemeral audio stream/token + actual voice language/provider |

Material/source DTOs add origin (`ui_upload`, `ui_link`, `drive_drop`), source_language, storage_state and preserved source identity/revision. Never route a UI upload from an arbitrary client folder_id. UI/Drive sync meet on the same `(owner, collection, drive_file_id, provider_revision)` and don't duplicate extraction. Local mode returns explicit local-only status. Source link descriptors conform to contracts/link-source.schema.json. All asynchronous jobs expose stage/progress, bounded retry and final durable provider confirmation, rather than a misleading immediate 'uploaded' message.
