# Deployment contract and release gates

Dockerfiles, Compose targets, migrations and CI are implemented. Local checks establish build and configuration behavior; a hosted deployment remains pending. The current goal is an invited connected beta for feedback. See [the hosted beta handoff](HOSTED_BETA.md) for the remaining account configuration and launch sequence.

## Required generated deployment files

`deploy/frontend.Dockerfile`: multi-stage pinned Node image, `npm ci`, Next build and production non-root start (standalone only if supported/tested with this version). `deploy/backend.Dockerfile`: pinned Python 3.12 image, frozen `uv.lock`, non-root FastAPI and separate worker command. Reproducible image versions/digests recorded after build; no invented digests here.

`deploy/compose.demo.yml`: frontend, backend, one worker, SQLite/private-file volumes, loopback-only ports, fake provider and visible demo banner. `deploy/compose.production.yml`: HTTPS edge (Caddy or equivalent), frontend, backend, worker, migration one-shot; PostgreSQL and private S3 endpoint may be externally managed. Production no source-code bind mounts, no public database/storage admin ports, health checks/resource limits/restart policies. Provide an explicit local PostgreSQL integration profile for repeatable tests. `deploy/Caddyfile`: actual domain via secure non-secret configuration; `/api/v1/*` proxied unchanged to backend, other routes to frontend, TLS and appropriate security headers. Never turn off verification to connect.

`deploy/.env.production.example`: names and non-secret placeholders only. `scripts/release_check.sh`, `scripts/backup.sh`, `scripts/restore_check.sh`: refuse dangerous ambiguous targets, preserve command exit status and verify actual outputs. `.github/workflows/ci.yml`: frozen installs, lint/typecheck/build, offline backend tests, PostgreSQL integration/migrations, Playwright and schema checks; synthetic fixtures only. Separate release workflow with minimal permissions, trusted branch/ref and deployment approval, never fork PR secrets. CI does not silently call a paid provider.

## Settings needed before a public release

| Setting | Purpose |
|---|---|
| APP_MODE=production; APP_ORIGIN | Mode and exact HTTPS origin |
| DATABASE_URL | PostgreSQL connection, secure secret storage |
| OIDC_ISSUER / OIDC_CLIENT_ID / OIDC_CLIENT_SECRET | Actual standards-compliant sign-in provider; issuer and ID non-secret |
| SESSION_SIGNING_KEY / TOKEN_ENCRYPTION_KEY | Server session and connector-token protection, securely generated |
| LEARNING_OS_API_KEY / LLM_MODEL / LLM_PROVIDER | Real server-side AI provider; model selected and verified |
| STORAGE_ENDPOINT / STORAGE_REGION / STORAGE_BUCKET | Private S3-compatible object store |
| STORAGE_ACCESS_KEY / STORAGE_SECRET_KEY | Least-privilege object credentials |
| DRIVE_CLIENT_ID / DRIVE_CLIENT_SECRET / DRIVE_REDIRECT_URI | Learner OAuth for folder/create/upload/read operations; verified direct-drop scopes, consent/testing or verification status |
| PUBLIC_DOMAIN / TLS settings | DNS and HTTPS on the selected host |
| DEFAULT_TIMEZONE / DEFAULT_LOCALE | Initial preferences (Africa/Lagos and en default, editable per learner) |

Existing bindings are inspected/reused before asking for these. Secrets go into secure environment settings. The current onboarding proxy reserves some variable names (including `OPENAI_*`); use the non-reserved Learning OS key name and initialize the SDK with it explicitly. Proxy-only placeholders may work only on allowed HTTPS destinations; never interpret them as a local raw token.

## Network requirements: additions to review, not replacement of unknown policy

Package managers use their preset registry hosts. Official version-sensitive docs need `developers.openai.com` if the policy permits. Runtime AI normally needs the actual selected provider API hostname (e.g. `api.openai.com`), Drive APIs/OAuth need the actual verified Google endpoints (commonly `www.googleapis.com`, `oauth2.googleapis.com`, `accounts.google.com`), and source links need the approved example domain(s). Caption access depends on the authorized adapter and cannot be enabled by a blanket domain guess. OIDC issuer, object-store and database host are host/account-specific. Preserve existing custom allowlist entries; add only observed required destinations through supported configuration. Git read success is not proof of any of these permissions.

## Ordered release sequence

1. Finish application and live connected gates; inspect original dashboard fidelity. Freeze release commit/images/locks, release mode and known limitations. All dependency findings triaged.
2. Run offline suite, PostgreSQL integration/migrations, two-user isolation, browser routes/voice checks, worker crash/idempotency, load targets and source/injection limits. Resolve unexplained failures.
3. Restore a backup to isolated resources and compare counts, citation/source hashes, history and review state. Rehearse rolling back to prior image with backward-compatible additive migration; never assume arbitrary downgrade is safe.
4. Populate real account/domain secrets securely, verify connectivity, migration permissions and private object policy. Generate a reviewable config diff and exact deployment command for the chosen host. No account creation/spend/publication without authorization.
5. User approves public deployment if not already authorized. Apply migrations as one release step, then start API/worker/frontend/edge. Verify HTTPS, login, private upload/citation read, study submission, review persistence and worker restart with synthetic accounts.
6. Record release result and monitoring/backup owners. Roll back according to tested plan if verification fails; retain failed-release evidence without exposing learner data.

For Codex cloud reuse, execute actual setup locally first. Then save a complete tested install_script (working directories/frozen installs/migrations) and start_skill (process startup/functional readiness) to the environment draft using the onboarding tool. Start instructions use the existing checkout and warn that snapshots retain files, not live processes. Saving a draft is not publication or a successful fresh-task restore; report each separately. This document itself does not save or apply those fields.

## Revision 2 release dependencies

Drive consent configuration supports app-managed writes and manually supplied file reads; verify actual scope behavior and any restricted-scope verification/testing-user limits before public multi-user release. Do not publish with test-account-only OAuth while calling it available to every client. Server speech provider/model/voice IDs and verified languages are secure runtime settings; model keys remain server-side. Bundle reviewed locale catalogs and licensed multi-script fonts locally; exact asset size/cache tests retained.

Live release report includes L01–L05 language/UI/study/STT/TTS evidence per target, D01–D06 folder/write/drop receipts, missing provider/region capabilities and credential/action requirements. Basic credentials can be absent during independent implementation; they remain genuine live release prerequisites. Raw source/Drive writes and speech use are authorized by explicit learner consent/user actions, not automatic account-wide access.
