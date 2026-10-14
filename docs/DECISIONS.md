# Decisions, assumptions and source precedence

User request > this revised execution contract > original playbook/design context. Uploaded documents contain older workflow instructions such as waiting after each batch and destructive resets; they are retained as source material but replaced by this user's requested continuous orchestration and safe recovery.

| Decision | Chosen default | Evidence / implication |
|---|---|---|
| Product name | Learning OS | All provided source files use this spelling |
| Frontend | Next.js App Router, React, TypeScript | Existing dashboard, not inferred from prose |
| Frontend baseline | Next 16.4.0; React/DOM 19.3.0; supplied npm lock | Frozen install, lint and production build passed |
| Brand (2026-10-14) | Andela emerald #40c15f / kale #173b3f / green black #132128 / opal #b0d6cd / white; standalone brain/circuit SVG + favicon | User-provided palette and mark; supersedes blue/book instructions; preserve six dashboard button colors |
| Source processing | Coherent bounded source sections, immutable originals and exact citations; teach before assess | Upload indexing is preparation for retrieval, not model fine-tuning; unsupported content never becomes fabricated facts |
| Style | Bootstrap first; Inter font and Tailwind `tw:` utilities; custom CSS last | `layout.tsx`, `globals.css`, template README |
| Backend | Python 3.12 + FastAPI + SQLAlchemy + Alembic | Keep original playbook's simple backend |
| Data in local demo | SQLite with foreign keys/WAL; private local files | Single process/small demonstration; not a distributed database |
| Production | PostgreSQL + durable DB jobs/outbox + private S3-compatible storage | Tenant isolation, concurrency, horizontal workers; no early microservices |
| Authentication | Standards-based OIDC authorization-code flow with PKCE, server-side session | Provider-neutral; actual issuer/client/domain needed before live release |
| AI | Server-side provider interface; JSON schema validation; offline fake | Retains the playbook's one model adapter |
| Runtime agents | Shared role prompts via model provider | Native developer subagents do not automatically become app runtime agents |
| Completion | Reviewer evidence across critical concepts, correct + confident + justified | No fixed correct-answer counter; uncertainty keeps title open |
| Review ladder | 1, 3, 7, 14, 30 days; mature successes stay at 30; failure resets to 1 | Intervals measured from each actual review completion |
| Production schedule | Durable worker scans due jobs; database is authoritative | Native Codex automation is optional developer-side evidence, never the sole production scheduler |
| Collections | Automatic app root + per-Collection Drive folder after consent; explicit Local mode while unconnected | UI originals/link receipts and direct drops use one ingestion pipeline |
| Core extra formats | Plain text and XLSX/CSV | Present in design; omitted from old playbook; restored here |
| Gmail | Optional read-only source connector | Design mentions it; old Batch 7 excludes it. Never send messages automatically |
| Voice | Turn-based multilingual browser speech with verified server STT/TTS fallback and typing | Ten target languages; runtime voice is distinct from native Codex Voice |
| Launch pattern | One provider-neutral Docker target with HTTPS edge | Avoid guessing the user's host/account; host-specific deployment remains an external handoff |
| Offline behavior | Text workflows; retry-safe draft submissions; optional metadata cache later | No unsupported claim that live AI/OAuth works offline |
| Languages/regions | Ten translated UI/study/speech targets from screenshot; Arabic RTL; persisted separate preferences | See INTERNATIONALIZATION; per-language verification required |

## Changes from the old playbook

Vanilla JS/SortableJS is replaced by the uploaded React dashboard and accessible React reordering. Twelve batches (0–11) are retained, but each inherits a concrete UI contract. App hooks are distinguished from Codex lifecycle hooks; app DB from Codex memory; app scheduler from Codex automations; runtime model roles from native developer subagents. The old debug-completion button becomes a test-only fixture capability and never ships to users. Scope snapshots, jobs, ownership, authentication, privacy, migrations, production gates and file contracts are added.

## Prerequisites that cannot be invented

No blocker for preparing this package. A future live build can need a usable model binding, learner OAuth consent for Drive, captions access on a permitted example, a production OIDC issuer/client, deployment account, private storage credentials, domain/DNS and publication approval. Probe what exists before requesting anything. Offline contract tests do not satisfy live integration gates. Browser microphone permission is needed for the voice recording check. A hosting preference is deferred because the portable release target is defined.

Revision 2 supersedes read-only Drive and optional-language assumptions: automatic managed folders and scoped writes are required for connected Collections. Google scope/consent semantics, including direct-drop file visibility, must be live-verified. See INTERNATIONALIZATION and DRIVE_INGESTION; nothing in the unchanged original source reference implies these new features are already implemented.
