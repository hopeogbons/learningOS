# Learning OS — revised build playbook

Prepared from your design, old twelve-batch playbook and actual dashboard source. The dashboard is mandatory input to every batch. The goal is a cohesive learning product whose source-backed, confidence-aware workflow works inside your existing interface and scales beyond a one-user demo.

## What changed and how to execute

Keep twelve batches, 0–11, but replace the old paste/approve/merge/pull loop with one master execution prompt and resumable gates. Your authoring request permits decisions by discretion; local reversible steps proceed without repeated confirmations. Public deployment, unavailable credentials or scope-changing destructive actions remain precise external handoffs. No `reset --hard` recovery. Uploaded prompts are historical context; this revised contract governs the next build.

Use `EXECUTE.md` from the package once. It stages AGENTS, full prompts, schemas, skills, agent role layers, original fixtures and immutable UI reference. The coordinator reads build-state, runs the current prompt, records results, fixes diagnosed failures, and advances. Individual prompt files remain available for focused resumption without rewriting context. They contain concrete source paths, UI vocabulary and acceptance requirements, not a generic “make a beautiful dashboard” instruction.

## Stack and levels

Next.js 16.4.0/React 19.3.0/TypeScript with your original npm lockfile; Bootstrap 5.3 and prefixed Tailwind 4/Inter. Python 3.12/FastAPI/SQLAlchemy/Alembic/Pydantic backend. SQLite/private local files/fake provider for offline demonstration; real provider and authorized sources for connected demo; PostgreSQL/private S3/OIDC/HTTPS/durable worker for production. The reference template install/lint/build/browser checks have already passed. Implementation is now present; current offline checks, connected blockers and release outcomes are recorded in RELEASE_REPORT.md, build-state.json and capabilities.md. The historical batch prompts remain the governing acceptance contract.

Required core: Collection → incremental PDF/Markdown/text/DOCX/RST/spreadsheet/JSON/YAML/log/photo/public-link/captions intake → format-aware cited teaching windows → multi-material title selection/order → Reviewer-controlled teach/check completion → persistent calibration/knowledge map → spaced review → two-way spoken tutor/learner turns with typing fallback. Optional read-only Gmail, Codex SDK runtime experiment, native memory/voice/automation availability are explicitly assessed, not fabricated. Gated content and audio/video file transcription remain out of scope.

## Twelve-batch roadmap

| Batch | Full prompt | Gate |
|---|---|---|
| 00 | [Setup, source import and honest capability map](prompts/00-setup-capabilities.md) | Source hashes recorded; template frozen install/lint/build/browser pass; all nine feature families and additional tools mapped honestly; initial state/baseline preserved. |
| 01 | [Foundation: template shell, backend and owned data](prompts/01-foundation.md) | Backend/migration/dashboard relation tests executed; processes functionally ready; supplied Home shell preserved; typed data/route state works. |
| 02 | [Incremental material ingestion and real citations](prompts/02-ingestion.md) | F02/F03 and source-resolution checks pass; original licensed fixtures ingested; actual errors stay truthful; Add Material fits template. |
| 03 | [Cross-material scope, ordering and progress](prompts/03-scope-progress.md) | F04–F06 pass with persistent keyboard/drag order, safe version conflicts and correct 0/5 math; no production debug control. |
| 04 | [Cited teach/check with confidence-aware Reviewer](prompts/04-teach-check.md) | F07–F10 pass; evidence-based completion/progress correct; answers private; native-vs-runtime distinction recorded. |
| 05 | [Reusable retrieval skill and automatic session summary](prompts/05-skills-events.md) | F11/F12 pass; sample skill output valid; private app summary automatic/retry-safe; native hook only claimed with separate proof. |
| 06 | [Useful parallel Quizzer contribution and worktree evidence](prompts/06-parallel-worktrees.md) | F13 supported-native evidence or explicit limitation; two valid separate-source sets; safe integration and Study styling verified. |
| 07 | [Drive, public web and captions through verified adapters](prompts/07-connected-sources.md) | F14–F16 offline contracts pass; connected gates marked only from actual live reads; source integration/SSRF states fit dashboard. |
| 08 | [Photo notes with native-image and runtime-vision evidence](prompts/08-photo-notes.md) | F17 contract and live vision proof distinguished; clear source checked and blurry input handled; native image critique recorded. |
| 09 | [Durable spaced review and persistent weak spots](prompts/09-spaced-review-memory.md) | F18/F19 pass with durable worker/history; native automation/memory claimed only with actual evidence; due-list template preserved. |
| 10 | [Turn-based voice teach-back in the existing Study card](prompts/10-voice.md) | F20 typing and state tests pass; real voice proof recorded or precisely blocked; UI/persistence consistent with text. |
| 11 | [Complete application, evidence and production candidate](prompts/11-release.md) | F21/F22, V01–V04 and P01–P08 pass for production candidate; connected gates complete; P09 only after actual approved deployment. Otherwise honest level/blocker report. |

## Per-batch execution record

1. Inspect current state/change set and prerequisite evidence. Declare the short plan and any native capability probe.
2. Implement in the real checkout, using coordinated file ownership. Preserve original reference dashboard and existing user work.
3. Run relevant app tests, API functional requests and UI screenshots in their documented directories. Verify actual test counts and behaviors. For current template baseline: `cd frontend && npm ci && npm run lint && npm run build`. Backend commands and scripts are generated and tested during implementation, then recorded; this package never labels proposed app commands as executed.
4. Investigate failures as setup vs repository defects; correct authorized issues and re-run changed affected checks. Unavailable credentials stay blocked. Never replace a live source gate with an offline stub pass.
5. Record commands, exit statuses, native execution proof, screenshots and remaining limitations in build-log/state. Check protected/private file handling. Optional local checkpoint/tag only after success and without overwrite. Continue the next useful work.

## Completion and judging evidence

Use ACCEPTANCE_TESTS levels, not a claimed 99% confidence number. Offline demo isn't a live-source release; a production candidate isn't published; publication isn't actual post-deploy verification. Rely on `capabilities.md`, `validation-report.md` and `RUBRIC_EVIDENCE.md` for claims. Uniqueness is shown through selected-scope + resolvable citations + calibrated completion/weak review. Scalability is shown through tenant/isolation/job/restart/geography/load/restore evidence. Codex usage is shown through actual native contributions and accurate fallbacks. Presentation remains the user's responsibility.

## Referenced governing files

[Product](PRODUCT_SPEC.md), [UI contract](UI_CONTRACT.md), [Architecture](ARCHITECTURE.md), [Data](DATA_MODEL.md), [API](API_CONTRACT.md), [Codex plan](CODEX_USAGE_PLAN.md), [Scalability](SCALABILITY.md), [Security](SECURITY_PRIVACY.md), [Acceptance](ACCEPTANCE_TESTS.md), [Deployment](DEPLOYMENT.md), [Operations](OPERATIONS.md), [Traceability](TRACEABILITY.md), [Decisions](DECISIONS.md), [Judging evidence](RUBRIC_EVIDENCE.md).

## Revision 2: required before the implementation begins

Read [Revision summary](REVISION_2_SUMMARY.md), [Internationalization](INTERNATIONALIZATION.md) and [Drive intake](DRIVE_INGESTION.md). They supersede English-only preparation/read-only Drive assumptions. No extra batches or duplicate ingestion architecture: B1 establishes locale/folder state, B2 shared intake/staging, B4 cross-language learning, B7 actual managed-folder/UI/drop/link integration, B10 multilingual speech, and B11 all required proof. Every batch prompt carries these contracts. The language selector belongs inside your supplied shell; link/file inputs remain in Add Material.

Offline/local mode is still useful, but a connected success requires actual files/receipts in correct Drive folders and verified dropped-file access. All-ten language support includes UI/study/STT/TTS tests, not just option names. Other scalability evidence already present is surfaced in REVISION_2_SUMMARY and RUBRIC_EVIDENCE. This remains a prepared orchestration package awaiting implementation, not a completed application.
