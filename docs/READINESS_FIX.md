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

## Follow-up verification

Readiness passed in GitHub CI and the browser suite moved beyond startup. It then exposed a stale selector: source extraction now retains full heading paths (for example `Original browser fixture / Atomic number`), while browser tests searched for bare `Atomic number`. The browser checks now resolve their fixture's actual source titles, exercise the same keyboard move, verify displayed ordering after reload and assert persisted source-ID order. The control-layout navigation check also uses the actual uploaded fixture title. This preserves meaningful reorder/navigation assertions without forcing production to discard heading context.

The initial restricted-cloud tokenizer failure was resolved by pre-caching the exact cl100k_base data from its public tiktoken-rs distribution on an allowed GitHub host, verified against tiktoken's expected SHA-256 `223921b76ee99bde995b7ff738513eef100fb51d18c93597a113bcffe865b2a7`. Subsequent full backend check passed: 200 passed, 3 PostgreSQL-fixture skips. No substitute tokenizer or proxy bypass was used. Public cache files require readable permissions for the container's non-root user and must be reprovisioned after container recreation on a restricted host; this operational cache is not a secret or tracked source artifact.

Cloud demo deployment: rebuilt backend/frontend, applied the additive forward migration without seeding, preserved the existing volume, then replaced API/worker/frontend containers. All services became healthy. Routed readiness returned 200, and a fresh synthetic Markdown upload was processed by the durable worker successfully. This is the existing cloud demo, not a public production or user-machine localhost deployment.

The connected-UI mock also needed the new `/ingestion/limits` response; an empty mock response correctly left uploads disabled. Its fixture now supplies a synthetic positive limit and includes a negative case proving upload submission stays disabled when the limits request fails. No production guard was removed to make a test pass. Local full E2E passed all 16 recorded checks, and consent UI passed 14 checks.

Final local browser gates passed: 16 full E2E checks, 10 connected-UI synthetic cases (including unavailable upload limits), 14 consent checks, and six translated collection/control cases plus six form widths. Full backend: 200 passed/3 PostgreSQL-fixture skips. Evidence summary: docs/evidence/readiness-fix/verification.json. Historical tracked screenshots are preserved; this run’s synthetic captures remain in work/readiness-browser-artifacts.

## Reproducible tokenizer dependency in fresh images

The core-demo Done when now requires backend/app/tokenizer_cache.py to provision the exact public cl100k_base asset during the frozen Docker build. The permitted public GitHub distribution is checked against tiktoken's SHA-256 above, bounded to 2 MiB and loaded using the real encoding before the build succeeds. Runtime inherits the prepared readable cache. No credentials, learner source or live network call is required to tokenize after container creation. This replaces manual cache-copy deployment steps; corrupted/unavailable build data fails explicitly.
