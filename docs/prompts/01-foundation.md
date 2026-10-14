# Batch 01: Foundation: template shell, backend and owned data


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, Andela green palette from UI_CONTRACT (emerald #40c15f, kale #173b3f, green black #132128, opal #b0d6cd), 264px desktop sidebar, 992/1400 breakpoints, green mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Build Python 3.12 FastAPI, SQLAlchemy, Alembic and Pydantic under backend/. Pin dependencies via pyproject.toml/uv.lock; deterministic tests and fake provider are default. Implement the core plus ownership/session/scope/revision/job tables specified in DATA_MODEL; introduce staged migrations rather than create_all-only production schema. Add /api/v1/health, /ready, collection CRUD, /me and dashboard snapshot; safe local demo identity only when APP_MODE=demo. Set up auth interface and production fail-closed settings; real OIDC can be completed at release gate.

Keep the copied Next.js App Router template as frontend. Extract AppShell from its existing page/chrome without changing its look. Route menus as specified, preserving Sidebar/BottomNav/MobileHero and active states; flesh out loading/empty/error pages in existing card language. Replace mock learner/counts with typed demo backend DTOs, separate icon metadata from serializable data; use same-origin API rewrite for development. Hardcoded statistic fill bars without a defined quantity should be omitted or labeled decorative. Add only interactivity-required client boundaries.

Create scripts/setup.sh and scripts/dev.sh (frozen installs, migration, API+worker+web; stop only their own processes). Test relation ordering and tenant ownership, migration from an empty SQLite DB, real backend dashboard request and Home browser rendering. Compare original static chrome at mobile/desktop. No cloud preview URL. Record mode and tests, then continue.


## Done when

Backend/migration/dashboard relation tests executed; processes functionally ready; supplied Home shell preserved; typed data/route state works.

## Useful delegation

Backend and frontend contributors may run in parallel after schemas are coordinated; read-only fidelity reviewer.

## Revision 2 batch work

Add language preferences/catalog framework and accessible chooser in existing topbar/Profile/mobile drawer; create complete message keys and ten catalog candidates with reviewed-status gate. Add folder/provisioning/upload-origin/remote receipt fields and local/Drive collection states to the initial migrations/DTOs. Server renders locale/dir, logical RTL shell and local script font fallback. Future Drive connection queues owned root/Collection folders; local demo remains explicit.

## Reproducible control layout and labels

Follow UI_CONTRACT’s 2026-10-14 control rules: vertically/horizontally center button content across full 44px hit areas, preserve existing colors, balance inputs and verify mobile/desktop/long/RTL labels. Collection detail links read Explore collection (localized), keeping the existing outline route/state intact. Run tests/control_layout.py on the fresh running demo; a screenshot or min-height declaration alone is not a pass.

Readiness regression: freshly upgraded Alembic databases must become ready with a fresh worker heartbeat; outdated/unknown/incomplete schema heads stay 503. Resolve expected revisions from the shipped migration graph, not a literal ID. Check the same-origin frontend readiness route before browser tests.
