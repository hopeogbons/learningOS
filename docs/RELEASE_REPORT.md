# Learning OS build and release report

The requested application is implemented in this checkout with the supplied Next.js/React/TypeScript dashboard and Python/FastAPI backend. The release is an **offline demonstration candidate**. All twelve batches were attempted; connected and production gates remain explicitly blocked. No public deployment or GitHub publication was performed.

## Verified application and development workflow

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

Real model text/vision, all-ten teaching and STT/TTS/proficient review, real learner Drive consent/folder placement/manual drops, permitted captions/public-page fetches, production OIDC/private S3 policies, domain/DNS/HTTPS and post-deployment checks remain unrun. Secure credentials/model identifiers are absent. Public-page fetches require a network path that supports safe DNS validation and pinned verified TLS; queued links do not prove a fetched page.

See LIVE_VERIFICATION.md for opt-in provider probes and Drive checks. Enter credentials through secure environment/deployment settings, never chat. The cloud proxy key is suitable only for its configured HTTPS destinations; raw session/encryption/storage credentials use the deployment's secure local secret mechanism. The all-ten launch claim remains blocked until L03/L04 and other connected gates actually pass. Study/speech language mismatches currently have an explicit unavailable/typing path, while matching-language regional variants are supported targets.

## Reviewable deployment

README.md contains the frozen setup/start/check commands and production review command. Production Compose uses externally managed PostgreSQL/private S3, runtime OIDC, separate API/worker/migration services and a same-origin HTTPS edge. Fill the private environment file and immutable registry image references for the selected host, then run:

```bash
scripts/release_check.sh --production /absolute/private/production.env
```

After the failed latency target and required live gates are resolved, public deployment can be reviewed using the prepared command in README.md. Domain/account/spending/publication choices have not been invented. The final source commit and archive hashes are recorded in the downloadable RELEASE_MANIFEST.json; local commits are also preserved in a Git bundle because remote publication and fresh-task local-commit restoration are unverified.
