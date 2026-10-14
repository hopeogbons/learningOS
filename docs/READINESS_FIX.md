# Migration-aware startup readiness — 2026-10-14

## Confirmed defect

The local update added migration `0003_material_delete`, but `/api/v1/ready` still compared the database with literal revision `0002_durable_guards`. A correctly migrated database therefore returned 503 with `database: migration-required`. The CI browser-stage wait also fell through after 90 unsuccessful readiness attempts, starting E2E against an unready application. The later service-exit line is not sufficient evidence of a separate worker failure.

## Durable correction

Readiness discovers the heads of the shipped Alembic graph and compares them with every row in the database version table. Behind, unknown and incomplete multi-head states remain 503; a fully upgraded database becomes ready when its worker and required runtime dependencies are ready. Expected heads are resolved from this backend's absolute migration directory, independent of shell working directory. No historical revision constant is used. Actual upgrade/rollback tests also compare against the shipped graph rather than pinning one revision.

The development launcher checks readiness through the frontend rewrite as well as directly. CI records whether its bounded wait succeeded and aborts before browser tests on timeout. It prints only sanitized dependency-state JSON; private logs and credential values are not exposed. No database reset, volume deletion, seed change or readiness bypass was used.

## Reproduction and validation

- `/workspace/learningOS`: `APP_MODE=test backend/.venv/bin/python -m pytest -q backend/tests/test_readiness.py backend/tests/test_migrations.py backend/tests/test_worker_health.py --tb=short`: 15 passed, 1 skipped (PostgreSQL URL not supplied), exit 0. Includes an actual fresh Alembic SQLite upgrade and readiness response, old/unknown revisions, later-release multi-head state, partial head rejection and worker health.
- `/workspace/learningOS`: isolated `scripts/dev.sh` with APP_MODE=demo, private runtime work/readiness-fix, API8058 and frontend3058: startup succeeded. HTTP readiness through both origins returned 200 with database/worker ready and offline-demo model.
- `bash -n scripts/dev.sh` and `git diff --check`: passed.
- Full local backend attempt: 186 passed, 14 failed, 3 skipped; the failures require first-use cl100k_base tokenizer data from openaipublic.blob.core.windows.net, denied by this environment's destination policy. This is a separate environment dependency and is not a passing full-suite claim. Required-network policy was not bypassed and no fake tokenizer was substituted. GitHub CI verification is tracked separately.

## Fresh-build rule

AGENTS, ARCHITECTURE, OPERATIONS, ACCEPTANCE_TESTS and the foundation build prompt require this behavior. Every migration must pass the actual fresh-upgrade readiness regression. Browser verification requires successful same-origin readiness and must never continue after the startup budget expires. Preserve learner data and follow forward migration procedures when a database is genuinely behind.
