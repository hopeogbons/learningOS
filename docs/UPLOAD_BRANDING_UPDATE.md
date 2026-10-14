# Learning OS upload, source preparation and branding — 2026-10-14

Changes are applied to the cloud checkout; no public deployment, remote push or modification of the user's running localhost app was performed.

## Implemented

- General theme uses Andela green black #132128, kale #173b3f, emerald #40c15f, opal #b0d6cd and white. Original six dashboard quick-action colors and Bootstrap button variants are preserved.
- A hand-traced standalone brain/circuit SVG replaces the framed book logo. Internal cutouts are transparent. The same mark supplies SVG/ICO favicons and a reusable public SVG.
- New PDF/Markdown/text preparation uses bounded 4,000-character retrieval chunks, preferring paragraph/sentence boundaries within original pages/Markdown headings. Fixed original line numbers when leading blank lines were stripped. Exact source excerpts and offsets remain traceable; old source revisions/scopes are preserved.
- Citation downloads already use the privately retained original file; byte-for-byte recovery was verified through the real browser upload flow.
- Updated AGENTS, product, UI, architecture, data, API, operations, acceptance, decisions, internationalization and all twelve build prompts so rebuilds preserve the requested behavior.

## Checks executed

| Check | Working directory / command | Outcome |
|---|---|---|
| Backend regression suite | /workspace/learningOS/backend: APP_MODE=demo .venv/bin/pytest -q (local network enabled) | exit 0; 178 passed, 3 skipped (PostgreSQL fixture unavailable) |
| Frontend lint | /workspace/learningOS/frontend: npm run lint | exit 0 |
| Frontend production build | /workspace/learningOS/frontend: NEXT_TELEMETRY_DISABLED=1 LEARNING_OS_DIST_DIR=.next-brand-build npm run build (local network enabled) | exit 0; compilation, TypeScript and 16 pages passed |
| Actual browser PDF intake | /workspace/learningOS: APP_MODE=demo python work/verify_small_pdf.py (local network enabled) | exit 0; synthetic 9,216-byte PDF HTTP 202, durable worker succeeded, UI Ready, outline/page-1 citation, exact original bytes |
| Responsive brand check | /workspace/learningOS: node work/branding/visual.cjs (isolated demo at 3052) | exit 0; 360/390/768/991/992/1440 Home and 390/1440 Upload, no horizontal overflow or browser page errors, exact six action colors |
| Root screenshot inspection | Home 390/1440, PDF upload desktop, transparent favicon PNG | green chrome, familiar layout, no enclosing logo frame, readable upload receipt/status |
| Independent native review | read-only reviewer | no blocking finding; original line-range fix verified |
| Diff/reference preservation | /workspace/learningOS: git diff --check; git diff --exit-code -- reference/dashboard | exit 0 |

## Limitations and next diagnosis

The user's particular 9 KB PDF failure was not reproduced. The uploaded original/error/status/origin was not available. No upload-route or worker fix is claimed: the reproduced valid small PDF succeeds. Need the failed request/job error or the actual PDF to diagnose its failure. Encrypted/unreadable/textless PDFs correctly need attention; file size alone is insufficient. Live Google Drive placement/consent was not tested and existing release blockers remain unchanged.

Chunking is page/heading-aware paragraph/sentence splitting, not a verified semantic topic classifier. Retrieval speed was not benchmarked. Source preparation means extraction/indexing before teach/check, not model fine-tuning. Existing original-source safeguards remain in force; future study generation cannot treat source text as system instructions.

To update an existing connected localhost installation, apply these source changes and rebuild using its existing documented launcher (bash scripts/local.sh start, or the Windows launcher), keeping its private configuration/data intact. Cloud file changes do not automatically replace an existing Docker image. Fresh Next build directories were used during verification to avoid stale cached CSS. No database reset/seed was used.

The designated chat output directory was unavailable on this attached executor (missing /codex parent; creation denied even with escalation). The reusable logo/favicons and verification report remain in this repository; no downloadable chat artifact is claimed.

## Follow-up deployment — 2026-10-14

User explicitly authorized merge and deployment. PR #1 merged into GitHub main at `b759a3c60dae75076eb1748e934845c0b470b388`. Rebuilt both Docker images and updated the existing `learningos-github-review` cloud demo stack, preserving its data volume and skipping seed/migration replay (`up -d --no-deps --no-build --wait backend worker frontend`). Retained pre-update images under `before-green-update` tags. All three services became healthy. HTTP health/readiness/logo/SVG checks returned 200; actual browser CSS was #173b3f. A fresh synthetic 9,216-byte PDF browser upload reached Ready and its page citation returned the exact original bytes; no browser errors.

Target is the existing cloud-local demo instance on frontend port 3150, API port 8150. This does not establish a public HTTPS production deployment or update a separate user-machine localhost instance. Public hosting remains unconfigured as documented in HOSTED_BETA.md. The specific reported PDF failure remains unresolved.

## CI contract correction — 2026-10-14

GitHub CI failed because `maintenance_updates` was added without updating the strict build-state schema. Extended the schema with optional, explicitly typed maintenance/backend/deployment records while preserving rejection of unknown fields. Added five regression cases covering the current published state, legacy state and invalid evidence. The validator now emits concise field-level errors instead of dumping the entire state. Local validation passed all six schemas and the ten-language registry; backend suite: 183 passed, 3 PostgreSQL-fixture skips. The correction affects orchestration validation/tests/documentation; deployed application behavior is unchanged.

The schema correction at `bac4e0d94d21feef6a8892dbdc96f03d5b22678e` passed both GitHub Actions jobs (offline/browser and PostgreSQL), run https://github.com/hopeogbons/learningOS/actions/runs/38546681887.
