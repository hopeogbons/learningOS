# Implementation coordination

All teams follow Revision 2. Coordinator owns cross-team integration, evidence and final validation. Existing cloud checkout is the task root; do not start privileged Codex processes or modify another contributor's owned files.

## Shared Python interfaces

Backend core creates `app/db.py`: `Base`, `SessionLocal`, `engine`, `get_db`; `app/settings.py`: `settings`; `app/auth.py`: `get_learner` returns owned `Learner`; `app/models.py` contains spec entities. Core publishes model names/fields immediately. Routers in separate files use `router = APIRouter()` and core mounts at `/api/v1` (router paths exclude that prefix). Sessions are synchronous SQLAlchemy; UUIDs represented as strings and JSON-backed fields for source/agent payloads. Explicit UTC conversion for SQLite naive timestamps.

`app/jobs.py`: `enqueue(db, learner_id, kind, payload, idempotency_key=None)` returns Job; registry `register(kind, handler)` where handler takes `(db, job)` and writes a JSON result. `app/worker.py` imports router/module handlers and calls `run_once()`; core owns leases/retry/commit. Agent modules register handlers without modifying worker/main.

Owners: core owns settings/db/models/auth/jobs/worker/main/core_api/seed/migrations/pyproject/lock; learning owns llm/learning_api/sessions/review/runtime prompts/learning tests; ingestion owns ingest/ingestion_api/storage/source adapters/speech endpoints/source tests. Message core early if interface needs change; do not independently alter shared models/requirements.

## Shared frontend interfaces

Frontend UI agent owns existing components, AppShell, routes, API client and interaction code. Localization agent exclusively owns `frontend/src/i18n/` and its tests/font assets; does not edit UI/routes. Export `I18nProvider`, `useI18n()` with `{t(key, values?), locale, setLocale(locale)}`, `languages` and `messages` registry. UI exports key inventory early; both coordinate to avoid untranslated strings. Locale changes persist via `/me`; user study/speech preferences edited separately in Profile. Frontend consumes actual OpenAPI DTOs and backend API; coordinator resolves contract mismatches.

Release agent owns scripts except existing hook helper, deploy/, .github/, README.md and operations test utilities. No backend/frontend code edits. Coordinator owns docs state/capability/release evidence. Independent review runs after integration; findings are assigned to relevant owner.

## Process

Implement the dependency-order foundation before dependent functional gates. Teams may prepare independent later components concurrently; batch state only advances after actual gate evidence. No live provider/OAuth/key values currently supplied; build meaningful fake-provider/adapter contracts and expose explicit unavailable states. Required live checks stay blocked, not passed. All ten locale catalog/layout checks can execute locally; live multilingual grading/STT/TTS need actual provider tests.
