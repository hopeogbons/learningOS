# Learning OS

Learning OS turns your own source material into cited teaching, recall checks, confidence-aware assessment and spaced review. The Next.js/React/TypeScript frontend preserves the supplied Learning OS dashboard; Python/FastAPI, SQLAlchemy and durable database jobs implement the learning workflow.

For the user-selected **localhost connected review**, follow [the local staging guide](docs/LOCALHOST_STAGING.md). It supplies private, non-overwriting settings initialization, exact Google callback registration, sign-in/Drive consent, and startup using the original frozen locks. Real text/vision and synthetic speech endpoint checks now pass; native-language/voice review, Drive consent, and production gates remain separate.

The current release level and exact passed/blocked gates are recorded in [the release report](docs/RELEASE_REPORT.md), [build state](docs/build-state.json) and [capability evidence](docs/capabilities.md). Offline tests and translated catalogs do not establish live multilingual study/speech or real Google Drive folder/write/drop access.

## Run the offline demo

Use the existing checkout in a Codex cloud task. Do not create a worktree for ordinary setup. A fresh machine needs Git, Node.js 24.19.0, Python 3.12.14 and uv 0.12.23; Docker is optional. The frontend uses its supplied `package-lock.json`; the backend uses `uv.lock`.

```bash
cd /workspace/learningOS
scripts/setup.sh
scripts/seed.sh
scripts/dev.sh
```

The implementation is currently a local review candidate; GitHub publication has not been performed. For the downloadable source archive, safely extract it, change into its root, then run the same scripts. Seed is idempotent, synthetic and restricted to demo mode. In the existing cloud checkout start from `scripts/setup.sh`; snapshots retain installed files and data, but running servers must be started again with `scripts/dev.sh`.

The local web listens on `http://127.0.0.1:3000`; the API listens on loopback port 8000. The dev script starts API, durable worker and web, checks functional readiness, and stops only its owned child processes on exit. This local address is an internal verification endpoint; a browser on another computer needs the cloud platform's authorized preview/port forwarding. It is not a public deployment URL.

Demo mode has a visible banner, deterministic fake AI, one synthetic learner, SQLite and private local object files. Default runtime files are under the ignored `.runtime/` directory. Never commit that directory, secret files, uploaded sources or voice/transcript data. Override `LEARNING_OS_RUNTIME_DIR` to keep private state outside the checkout.

## Verify the build

```bash
scripts/check.sh
scripts/security_check.sh
# With API, worker and web already running, and Playwright/Chromium installed:
scripts/check.sh --browser
```

The default command runs actual backend tests, migrations, locale contracts, lint, TypeScript and the production web build. The opt-in browser command exercises UI behavior against running services. Install the pinned browser tooling into an isolated environment if needed:

```bash
python -m venv .runtime/browser-tools
PIP_CACHE_DIR=/tmp/learningos-pip-cache .runtime/browser-tools/bin/python -m pip install playwright==1.56.0 httpx==0.28.1
.runtime/browser-tools/bin/python -m playwright install chromium
BROWSER_PYTHON="$PWD/.runtime/browser-tools/bin/python" scripts/check.sh --browser
```

PostgreSQL contract tests use isolated synthetic data, never a live learner database:

```bash
docker compose -f deploy/compose.postgres-test.yml up -d --wait
export DATABASE_URL='postgresql+psycopg://learningos_test:synthetic-local-integration-only@127.0.0.1:55432/learningos_test'
export TEST_POSTGRES_URL="$DATABASE_URL"
scripts/check.sh --postgres
docker compose -f deploy/compose.postgres-test.yml down
```

The CI workflow uses frozen installs, offline fake providers, browser behavior and PostgreSQL migrations/contracts. Fork PR checks do not receive deployment secrets or make paid model calls.

## Container demo

```bash
scripts/build_images.sh
docker compose -f deploy/compose.demo.yml up -d --wait
docker compose -f deploy/compose.demo.yml exec backend python -m app.seed
docker compose -f deploy/compose.demo.yml down
```

Demo ports bind to loopback, and data is retained in a named volume. `down` leaves that data intact. Avoid `down -v` unless you deliberately want to delete synthetic demo state. The build helper reuses existing proxy/trust configuration without printing or storing proxy credentials. On a trusted isolated development host whose Docker network requires it, use `LEARNING_OS_BUILD_NETWORK=host scripts/build_images.sh`; TLS and artifact hashes remain enabled. Do not apply that network option to untrusted source builds.

## Connected use and languages

`APP_MODE=live` is for a restricted, authenticated connected environment. Configure the actual provider/model and learner-consented integrations securely; never put keys in `NEXT_PUBLIC_*` variables. The backend uses `LEARNING_OS_API_KEY` and `LLM_MODEL`. The personal Codex Google Drive connector is separate from the application's per-learner OAuth connection. [Connected verification](docs/LIVE_VERIFICATION.md) provides explicit preflight/provider/Drive procedures; credentials go in secure settings.

The ten target languages are English, Simplified Chinese, Spanish, Arabic, Portuguese, French, Japanese, Russian, German and Indonesian. UI, study and speech preferences are separate; Arabic uses RTL. Original source citations and learner progress must survive language changes. Each language's actual live study/STT/TTS proof remains an independent release gate.

Connected Collections reconcile a managed Drive root/folder. UI file uploads and pasted links write to the selected Collection folder; direct folder drops enter the same deduplicated ingest pipeline. Pending/denied/offline states stay explicit. Local demo originals are private local files, with no claim of confirmed Drive placement. See [Drive ingestion](docs/DRIVE_INGESTION.md) and [internationalization](docs/INTERNATIONALIZATION.md) for live gates and scope/consent details.

## Backup and restore proof

Stop API/worker writes before taking a consistent database-plus-object backup. Use a new private output directory each time:

```bash
scripts/backup.sh --quiesced --output "$PWD/.runtime/backups/first-check"
scripts/restore_check.sh "$PWD/.runtime/backups/first-check"
```

The SQLite restore check copies to an isolated temporary database, verifies database/foreign-key integrity, compares every table's count/content signature, and checks private-object hashes. The manifest contains digests, not learner row values. Backups contain private content; encrypt them at rest, restrict access and apply a reviewed retention/deletion policy.

PostgreSQL backups additionally require matching `pg_dump`/`pg_restore` clients. Restore checks require a separate pre-created empty database whose name ends `_restore_check`, supplied as `RESTORE_DATABASE_URL`; the scripts refuse the source database and populated targets. Private S3 export uses the configured bucket's read access and produces hashed local object copies. The restore check never writes into a live S3 bucket. Actual production bucket restore/policy, PostgreSQL restore and previous-image rollback must be rehearsed before public release.

## Prepare production for review

The portable target is PostgreSQL, private S3-compatible storage, OIDC sign-in, real AI, API/worker containers and same-origin HTTPS Caddy. PostgreSQL/S3 endpoints are externally managed; the production Compose file exposes only HTTP/HTTPS and no database/storage-admin ports. It contains no source-code bind mount. The edge preserves `/api/v1/*` unchanged.

Copy `deploy/.env.production.example` to a private path outside Git, protect it with `chmod 600`, and set real settings through the deployment's secret mechanism. Required values include domain/DNS, verified OAuth/OIDC/provider connections, session/token keys, private storage credentials and reviewed immutable application image digests. Empty example values are intentional. Never paste secret values into chat.

```bash
scripts/release_check.sh --production /absolute/private/production.env
```

That command validates configuration without publication. Review [the deployment gates](docs/DEPLOYMENT.md), the release report, exact image references, security findings, backup/restore evidence and known limitations first. Only after explicit authorization on the selected host:

```bash
PRODUCTION_ENV_FILE=/absolute/private/production.env docker compose --env-file /absolute/private/production.env -f deploy/compose.production.yml up -d --wait
```

Set `PRODUCTION_ENV_FILE` to that same absolute private file when the Compose service env-file location differs from its default `deploy/.env.production`. Apply migrations once as the gated one-shot service. Verify HTTPS, sign-in, source upload/citation ownership, study/review persistence and worker recovery with synthetic accounts. `scripts/rollback.sh /absolute/private/previous-release.env` prepares a previous-image rollback for review; it never downgrades or drops the database or changes deployment automatically.

## Build contracts

- [Product and learning behavior](docs/PRODUCT_SPEC.md)
- [Dashboard design contract](docs/UI_CONTRACT.md)
- [Twelve-batch playbook](docs/BUILD_PLAYBOOK.md)
- [Security and privacy](docs/SECURITY_PRIVACY.md)
- [Scalability targets and required evidence](docs/SCALABILITY.md)
- [Judging criteria evidence](docs/RUBRIC_EVIDENCE.md)

Native Codex developer capabilities, app runtime model roles, app learning memory and durable runtime scheduling are separate. Capabilities are reported as exercised/configured/fallback/blocked with actual evidence; a configuration file alone is not proof of native execution.

Source-language labels can be specified on upload/link intake and corrected in Add Material. Unknown remains `und`; the application does not claim automatic detection for plain files. Corrections preserve original source bytes, hashes, citations and previous turn snapshots.
