# Learning OS build and release report

The requested application is implemented with the supplied Next.js/React/TypeScript dashboard and Python/FastAPI backend. The release is an **offline demonstration candidate** with preliminary live provider verification. All twelve batches were attempted; complete connected and production gates remain pending. The user requested access outside Codex, so the reviewed source was pushed to the initial `main` branch at https://github.com/hopeogbons/learningOS. Public application deployment remains unpublished.

## Hosted beta target and Drive connection correction

The user now requests a hosted connected beta to give feedback on real functionality. Public deployment is authorized, but no hosting destination/access, domain/DNS, Google sign-in registration or private production storage is available. `HOSTED_BETA.md` records the concrete launch handoff; no hosted URL exists yet.

Drive setup metadata now distinguishes offline demo, missing/invalid setup and configured consent. The UI explains setup requirements and disables unavailable actions; valid configuration starts OAuth with a CSRF-protected POST. Callback configuration is checked against the actual origin, and the production preflight rejects a mismatched callback or conflicting origins before launch. These checks do not establish real Google consent.

The current source passed **132 backend tests with isolated PostgreSQL, zero skips**, lint, TypeScript, the frontend production build, API contract drift and ten 266-key catalogs (23,940 ICU formats). Six desktop/mobile connection cases passed with intercepted Google consent, and four synthetic production preflight cases passed without external calls. Screenshots were inspected. Evidence: `docs/evidence/drive-setup/`. A connected-local Docker target is available as a fallback; full connected-container startup, real Google consent and target-host validation remain unrun. Existing native-language/voice and latency limitations remain.

## PostgreSQL CI correction

The reported six hosted-CI failures were reproduced with APP_MODE=test and provider keys removed. Test mode incorrectly selected the live provider; it now selects the deterministic fixture provider, just like demo mode. Live/connected/production still require real credentials and never fall back. Five new regressions protect both behaviors. The corrected no-key run passed 49 targeted source/provider tests and **121 full backend tests with real isolated PostgreSQL**, no skips, after frozen installation and migrations. Three upstream deprecation warnings remain; they do not cause these failures. See evidence/ci-provider-mode-fix.json and evidence/ci-postgres-no-keys.log. The hosted Actions rerun is a separate result.

The isolated test launch also exposed unquoted tmpfs option commas in YAML. Complete mount strings are now quoted in test and prepared production Compose; the actual PostgreSQL service became healthy and the production file passed a syntax/options check. No production deployment or dependency/lockfile change was made. Earlier container/source evidence below describes its captured source version; the updated GitHub source rebuilds normally with the documented --build command.

## GitHub access and Docker demo follow-up

The source is now accessible through the repository's regular Code → Download ZIP action. README supplies one Docker Compose startup command for the user's own computer, with no Codex/Node/Python/provider-key setup required for the offline demo. Current backend/frontend images were rebuilt and the isolated Compose stack started successfully. Initial `--wait` failed because the worker had no healthcheck; a container-local database heartbeat check now verifies only that worker's host, rejects stale/future timestamps, and returns failure without logging connection secrets. Both demo and prepared production Compose use it; no production deployment was made.

Seven worker-health regressions plus five provider regressions passed. The latest full backend run has **113 passed, 3 skipped** (the isolated PostgreSQL fixture was absent). The rebuilt stack passed same-origin readiness, original Home desktop/mobile rendering with no errors/overflow, and an actual browser upload followed by durable extraction and an original citation. New demo image IDs, input fingerprints, checks, and synthetic-only screenshots are in evidence/github-access-review.json and evidence/github-demo-container-source.json. The earlier full container rollback evidence remains historical; production registry references, live integrations, performance, and target-host validation are still pending.

## Connected follow-up: localhost selected

After credentials were supplied, model discovery succeeded and **42 real text/vision checks passed**: ten languages with one question plus correct/incorrect/low-confidence grading each, and clear/unreadable vision. **20 real speech endpoint checks passed**, one synthetic TTS→STT round trip per language. All ten transcripts passed the bounded source-keyword check. These are actual provider requests, not mocked transport. L03 proficient semantic approval and L04 native transcript/audibility/three-turn browser proof remain pending; the runtime speech allowlist was not enabled.

Live testing found and fixed two defects: constrained generation allowed an empty required source-quote list, and the provider rejected the review schema's `uniqueItems`. Teaching now requires a nonempty original quote; the outbound provider subset omits unsupported uniqueness keywords while authoritative local validation still rejects duplicate evidence/citations. Five regressions cover these boundaries. The latest full backend run reports **106 passed, 3 skipped** (the isolated PostgreSQL fixture was unavailable for this follow-up); the targeted provider/session run passed 26. Earlier PostgreSQL evidence below remains historical. Lint, TypeScript, ten 263-key catalogs, and the 16-route production frontend build passed.

Local connected API/worker/frontend startup passed with anonymous dashboard/Collection reads returning 401. The startup check now expects that authentication boundary, rather than requiring an anonymous successful dashboard. An actual sign-in link is translated in all ten catalogs; English/Arabic mobile browser checks passed without page errors or overflow. Local encrypted-token/session keys are generated privately by a non-overwriting helper. Google sign-in itself remains unverified: the supplied cloud Drive redirect is not a valid configured callback, there is no connected account, and a registered Web client plus learner consent are required.

Use [LOCALHOST_STAGING.md](LOCALHOST_STAGING.md) and the new source archive to run on the same computer as your browser. Raw keys, audio, transcripts, provider outputs, and consent data are excluded from that archive. Redacted results are in [evidence/connected-verification.json](evidence/connected-verification.json). There were 67 inference attempts including diagnosis; 42 final text/vision and 20 speech endpoint checks passed. The former container image digests and source archive below predate these fixes; do not use them as proof of the updated source or skip a new image build/review before production.

## Initial offline validation, before the connected follow-up

- 104 backend tests passed with no skips, including real isolated SQLite/PostgreSQL migrations, two-process PostgreSQL job claim/lease recovery, signed synthetic OIDC/PKCE rejection cases, ownership, quotas, idempotency, source citations, learning coverage and review scheduling. Three upstream deprecation warnings remain. The extra two-turn recording-provider regression verifies locale propagation, not translation quality.
- A source copy initially without node_modules or a virtual environment completed frozen installation and the full check script: the then-current 103 tests, contract validation, lint/TypeScript, all ten locale catalogs and the 16-route production build. Its source and private synthetic state were retained; disposable generated dependencies/caches were removed after validation to recover disk space.
- All ten catalogs have 261 keys, 23,490 ICU formatting cases and 230 licensed local font assets. Arabic RTL and original source/citation identity are preserved. Catalog text is an authored candidate, with proficient-language review pending.
- Real browser upload, link intake, scope selection, order persistence and independent language preferences are recorded in evidence/browser/results.json. An interrupted upload response reuses the same intake key. Source language can be supplied/corrected without rewriting original bytes, citations or prior turn snapshots. Unknown remains und; automatic file-language detection is not claimed.
- Dependency scans after supported locked upgrades reported zero known backend and production-npm vulnerabilities. Five high findings remain in the development lint chain (GHSA-vfj7-8cjw-p6xm); the inspected registry exposed no newer braces patch. The final standalone frontend runtime omits that lint chain. This is dependency evidence, not an OS/container certification.
- Independent native Codex reviews verified fixes for aggregate source quotas, concurrent local-write collisions, S3 credential mapping, storage/processing labels and material counts, and hardened session-owned speech. Browser mocks verify cancellation/fallback, not spoken-language availability.

## Containers and recovery

The final local images are backend sha256:23ce5f326038e4b70ce8b6f2267893c2e211f9d2d63003e94ad6da45413a7c34 and frontend sha256:c6aef39212a57f0a9e488e493ab6ba70de6e1033816e1c73211e4697293b93f1. Exact input hashes are in evidence/container-source-manifest.json.

Six isolated container checks passed: migration/seed/readiness, standalone JS/CSS and Arabic/CJK fonts, original-upload/citation/scope/answer flow, volume restart persistence, actual previous backend/worker/frontend rollback against additive schema 0002, and forward return. Original hashes, history, scope and source-language labels survived. No database downgrade or public publication occurred.

SQLite and isolated PostgreSQL backups restored all 23 table content signatures plus private-original hashes. A PostgreSQL rehearsal also preserved nonempty synthetic history and review schedule. Six backup safety tests passed. Backups and the two SHA-verified Docker image archives remain private under .runtime and are excluded from the source download.

This cloud uses Docker vfs, which duplicates filesystem layers. Concurrent builds/recreations temporarily filled its 32 GB disk and interrupted development renders. Disposable caches were cleared, incomplete generated output was rebuilt, and verified image archive swapping allowed the final cold rollback to pass. Those diagnosed failures are retained in operations-validation.json; they are not counted as passes.

## Measured scalability limit

The five-minute PostgreSQL run used 50 authenticated fixture learners, 5,000 titled sections, 50,000 concepts, two API workers and 20 actual ingestion jobs. It completed **35,350 requests, zero errors, p95 855.08 ms**, and all jobs succeeded once. The 500 ms target failed. Query batching improved throughput, but did not pass the latency gate. A bounded four-worker experiment also failed (2,126 requests, zero errors, p95 792.86 ms); no five-minute retry ran after that failed smoke.

The host had a four-CPU cgroup quota/32 GiB limit and other development activity. Loopback fixture authentication is not live OIDC or a worldwide provider benchmark. Further profiling/capacity work is required before P05 can pass. The portable PostgreSQL/private-storage/stateless-API/job design and ten-language UI are implemented; worldwide availability, provider costs and regional policies are not inferred from them.

## Required external gates

Real text/vision and all-ten synthetic speech endpoint checks now pass as recorded above. Proficient/native language review, actual browser voice exchanges, learner Drive consent/folder placement/manual drops, permitted captions/public-page fetches, production OIDC/private S3 policies, domain/DNS/HTTPS and post-deployment checks remain unrun. Provider settings are now usable; Google account registration/consent and production configuration remain prerequisites. Public-page fetches require a network path that supports safe DNS validation and pinned verified TLS; queued links do not prove a fetched page.

See LIVE_VERIFICATION.md for opt-in provider probes and Drive checks. Enter credentials through secure environment/deployment settings, never chat. The cloud proxy key is suitable only for its configured HTTPS destinations; raw session/encryption/storage credentials use the deployment's secure local secret mechanism. The all-ten launch claim remains blocked until L03/L04 and other connected gates actually pass. Study/speech language mismatches currently have an explicit unavailable/typing path, while matching-language regional variants are supported targets.

## Reviewable deployment

README.md contains the frozen setup/start/check commands and production review command. Production Compose uses externally managed PostgreSQL/private S3, runtime OIDC, separate API/worker/migration services and a same-origin HTTPS edge. Fill the private environment file and immutable registry image references for the selected host, then run:

```bash
scripts/release_check.sh --production /absolute/private/production.env
```

After the failed latency target and required live gates are resolved, public deployment can be reviewed using the prepared command in README.md. Domain/account/spending/publication choices have not been invented. The final source commit and archive hashes are recorded in the downloadable RELEASE_MANIFEST.json; local commits are also preserved in a Git bundle because remote publication and fresh-task local-commit restoration are unverified.
