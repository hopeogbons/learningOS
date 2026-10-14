# Local connected application health report

Docker supports the real application. The default `compose.yaml` now runs **live connected mode**, requires Google sign-in, and preserves a separate empty connected database. Demo is an explicit `deploy/compose.demo.yml` option. Git branch names and the build-state validation label do not select runtime mode.

No sample seed is required. A successful Google sign-in creates your learner; you then create your own Collections and upload content. Existing demo data, connected volumes and encryption keys are preserved. Do not delete volumes to solve a connection error.

## Connection diagnosis

The demo file forces `APP_MODE=demo` and does not load Google credentials. Registering endpoints in Google Console alone cannot change that. The connected file reads **`.runtime/localhost/localhost.env`**. A different project-root `.env` does not supply application credentials.

Connect is enabled when the server reports valid connected configuration. The disabled state is conditional; it is not permanently removed. Desktop/mobile browser tests verified that configured installations can start consent with POST and CSRF protection. A private file using native quoted keys is invalid for Docker's raw environment parser; the diagnostic now identifies those field names without revealing their values.

Use one hostname consistently in the private file and browser: `localhost` or `127.0.0.1`. The default Docker frontend listens on port **3000**, not backend port 8000. Both Google callbacks must match that browser origin:

```text
http://localhost:3000/api/v1/auth/callback
http://localhost:3000/api/v1/connections/drive/callback
```

Substitute `127.0.0.1` in both if that is your registered hostname. Set the OIDC and Drive Web-client IDs/secrets in the private file; the same Web client may serve both flows. Enable Drive API and allow your Google account on the consent screen. The app cannot verify your local registrations from this cloud workspace.

## Defects found and fixed

| Defect | Corrected behavior |
|---|---|
| Empty/partial private configuration left migration blocked | Initializer completes missing defaults/local keys while preserving existing values and legacy keys |
| Default startup led users into sample mode | Root Compose starts live mode; demo requires explicit selection |
| Compose replaced configured `localhost` with `127.0.0.1` | Private browser origins are preserved; unmapped ports/IPv6 fail diagnostics |
| Connected readiness hid missing sign-in configuration | Readiness reports OIDC/Drive setup and rejects missing sign-in configuration |
| New Collections defaulted to Local despite connected Drive | Drive is the default after connection; explicit Local choice persists |
| Collection created during folder provisioning could remain pending | Provisioning admission and final reconciliation include concurrent Collections |
| Transient token refresh failures were treated as revoked consent | Network/429/5xx failures retry; invalid/revoked authorization requires reconnect |
| Sleeping Drive scans could exhaust interactive queue capacity | Delayed maintenance has a separate bounded budget; manual work remains rate limited |
| Manual Sync promoted maintenance without admission checks | A new admitted manual job replaces the sleeping poll; rejection preserves the old poll |
| Upload and Study continued polling after completion | Terminal/awaiting-answer states stop polling; slow Study requests do not overlap |
| Cancelled upload jobs continued polling | Cancellation is terminal and has a translated status |
| Successful upload receipt kept displaying Upload pending | Receipt displays the worker's confirmed storage result |
| Failed consent ended at a raw JSON callback page | Valid-state failures return to Connections with translated guidance; invalid/replayed state is rejected |
| Sync could not recover a failed folder provision | Sync retries provisioning for unfinished folders and scans ready folders |

## Verified behavior

- **177 backend tests passed with isolated PostgreSQL, zero skips.** Includes signed OIDC identity/nonce/state checks, CSRF, tenant isolation, immutable scopes/citations, ingestion/deduplication, durable jobs, history/review and new defect regressions. These use deterministic providers/mock Google adapters.
- The connected Docker stack started in live mode with **zero learners** and no seed. Unauthenticated dashboard access returned 401. A test-only synthetic opaque session exercised actual authenticated API and CSRF behavior.
- Actual container-worker file intake, extraction, citation resolution, scope selection, **real AI question and assessment**, history/summary persistence and restart recovery passed. This proves the local runtime path; the synthetic session does not prove Google sign-in.
- Configured Drive PKCE initiation and declined-consent recovery passed through real containers without requesting Google tokens or writing to a Google account. The final configuration check was retested after port validation was tightened.
- Production frontend build, lint, TypeScript, API contracts and ten 270-key catalogs passed. Browser checks exercise Drive defaults, explicit Local selection, terminal/retry/cancelled states, slow-request concurrency, consent errors, enabled Connect, and folder recovery using intercepted synthetic responses. The full answer/review/advance/finish transition was also checked.
- Dashboard styling was preserved; desktop/mobile screenshots were inspected. Windows PowerShell launcher is supplied, but execution on an actual Windows machine remains unverified.

Evidence: `docs/evidence/local-connected-audit/`. Reusable UI regression scripts are `tests/local_connected_frontend.py` and `tests/local_consent_frontend.py`; CI runs them without real provider calls. The private cloud container probe made live AI calls; no credentials, learner content, source text, tokens or transcripts are in tracked evidence.

## What still needs verification or configuration

| Area | Honest current status |
|---|---|
| Your Google sign-in and Drive account | Not accessible from this workspace. Verify with your local Web client, exact callbacks and consent account |
| Actual managed folders, UI placement, direct drops, link receipts, revoked/moved files | Adapter regressions pass; live D01–D06 still require your connected Google account |
| Web links/captions | Safe-fetch guards pass. Permitted external retrieval/captions must be verified on the destination network; missing captions cannot be fabricated |
| Voice | Real synthetic STT/TTS endpoint probes previously passed. Native/audible/browser verification and configured model/voice/locale allowlist remain required; typing works |
| Ten-language quality | Catalog/RTL/state checks and prior live text probes passed; proficient/native semantic review remains pending |
| Sustained high-load latency | Earlier production-style load test missed the 500 ms p95 target. UI polling fixes do not certify that benchmark; it has not been revalidated here |
| Retry exhaustion | Four unsuccessful worker attempts become failed/Attention. Manual Sync, retry or reconnect resumes work; failures are not retried endlessly |
| Failed upload receipt storage badge | Processing failure may retain the initial storage badge when no result exists. The job Attention state and owned material storage status are authoritative; extraction failure does not imply a failed Drive write |
| Hosted production operations/security scans | Outside this local delivery: host-specific HTTPS/private storage, load, restore/rollback and outstanding audit findings remain in RELEASE_REPORT |

## Confirmed cause of the reported migration exit

The supplied migrate log reports every connected client/model setting, issuer, callback and protection key missing. This is the configuration preflight failing before Alembic runs. The private settings file was not loaded or is unfinished; Google Console registrations cannot populate it. Run the initializer, fill the six client/model fields privately, preserve generated keys and retry startup. No database seed, reset or volume deletion is indicated.

## Run your corrected installation

Update from GitHub while retaining your private file and volumes. If that file does not exist, initialize it with `docker compose --profile init run --build --rm --no-deps init` (Linux: add `--user "$(id -u):$(id -g)"` before `init`) and fill it privately.

```text
docker compose -f deploy/compose.demo.yml down
docker compose --profile diagnose run --build --rm --no-deps diagnose
docker compose up --build -d --wait
```

Stop at an incomplete diagnostic and fix the **listed names** in the private file. Open its configured browser origin and sign in, then Connect Drive and create your own Collection. No seed/reset is needed. To diagnose a remaining local failure, share only the diagnostic's mode, issue names and safe callbacks, plus the exact error; never send the private environment file, tokens, or secrets.
