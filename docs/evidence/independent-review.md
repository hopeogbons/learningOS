# Independent implementation review

Review date: 2026-10-13. Reviewer: native Codex collaboration task `/root/independent_review`, independent of the implementation owners. Scope: read-only application/security/release inspection and isolated synthetic reproductions. Only this report was edited by the reviewer. The working tree was still being integrated; findings below describe the inspected revision and need explicit fix/retest disposition before release.

This is **not a production-readiness approval**. Runtime AI, actual learner Drive consent and writes/direct drops, private S3 policy, live speech in all ten languages, and actual HTTPS deployment were not exercised by this reviewer.

## Remediation re-review

Implementation owners corrected the findings after the initial review. Independent targeted verification ran the five new source quota/storage regressions, Collection count/sync regression, and the complete owned-speech test module: **16 passed**, exit 0, two library deprecation warnings. This covered same-content concurrent atomic writes, declared S3 configuration and AWS fallback, UI-link snapshot quotas, direct-drop byte/count quotas, concurrent quota reservations, owned Collection count/timestamps, and the new session-owned speech controls.

| Finding | Current disposition | Evidence boundary |
|---|---|---|
| R1 quotas | Fixed in the inspected source; regression verified | Common learner reservation lock across UI/link/drop persistence; concurrent SQLite reservation test passed. Live provider behavior remains unrun. |
| R2 local race | Fixed; reproduced trigger now passes | Unique `mkstemp` file per call, atomic replacement and temporary cleanup. |
| R3 S3 settings | Fixed; configuration unit verified | `STORAGE_*` mapped to Boto3 arguments, default AWS credential chain retained. Live private-bucket policy still blocked. |
| R4 false Drive badge | Fixed in frontend source | Processing `ready` now labels Ready; recent materials show separate actual storage state. Fresh browser evidence is owned by coordinator; this reviewer has not recaptured the changed screenshot. |
| R5 material count/sync | Fixed; owned count/timestamp regression verified | Counts exclude archived sources and timestamps expose canonical/compatibility names. Batched Collection/revision loading also replaced measured N+1 reads. |

A broader interim source/core run had **44 passed, 1 failed**: the legacy speech-unavailable test still posted the removed generic speech URL and expected 503, while the new session-owned route correctly returned 404 for that URL. This integration test drift was reported to the coordinator/source owner. The targeted new owned-speech suite passed; a final full-suite run after adapting the legacy case is still required. The reviewer has not changed application or existing test code to conceal that failure.

The old finding descriptions below are preserved as the actual review trail, not current unresolved defect claims. Scalability probe evidence is tracked separately in `performance-*.json`; none demonstrates OIDC/provider/cloud-region availability.

## Executed validation

- Working directory `backend/`: `.venv/bin/python -m pytest -q tests/test_core.py tests/test_learning.py tests/test_sources.py tests/test_oidc.py` — exit 0, **62 passed**, one Starlette/AnyIO deprecation warning. No skipped cases in this selected run. Migration/PostgreSQL tests were outside this review run; coordinator evidence must cover them separately.
- Isolated in-memory SQLite, temporary private storage, mocked web extractor and stub Drive adapter: reproduced link/direct-drop quota bypass without network access or real credentials. With `SOURCE_QUOTA_BYTES=1`, a UI link stored 382 bytes, then a direct drop added four bytes, total 386.
- Isolated temporary private storage and two threads synchronized immediately before atomic replacement: identical concurrent `LocalStorage.put` calls returned `FileNotFoundError` and success. The stored source content remained valid; one requesting caller failed.
- Inspected original and implementation screenshots: `reference/screenshots/desktop.png`, `mobile.png`, and `docs/evidence/browser/home-1440.png`, `home-390.png`. Hero, sidebar, six action colors/order, card vocabulary and bottom navigation are recognizably preserved. The demo banner/language control are intentional visible additions. A quantitative static-chrome pixel-diff gate and all-route accessibility pass were not independently performed here.

## Findings sent to coordinator

### R1 — High: source quotas bypassed by link snapshots and Drive drops

At inspection, `backend/app/ingestion_api.py:46`–48 checked collection count and existing revision bytes before UI intake. Links had `data=None`, so their projected byte size was zero. `backend/app/ingest.py:172` subsequently persisted the fetched descriptor without another quota guard. `backend/app/ingest.py:249`–253 persisted newly discovered Drive originals/revisions without the UI aggregate byte or 1,000-material limit. Individual file caps do not enforce total learner storage quotas; repeated remote versions can also grow retained originals.

Reproduction: set the aggregate quota to one byte in an isolated database; admit a UI link, stub its fetch with one source paragraph, and run its ingestion. Sum `MaterialRevision.size`; observed 382. Configure a synthetic owned Drive folder/connection, stub a four-byte `drop.txt`, then call `sync_drive`; observed `discovered=1`, total 386. No external calls were made.

Required fix/retest: common aggregate quota reservation/check for all persistence paths, serialized per learner to prevent concurrent check/write races. Reconcile actual link size after fetching and before persisting. Test count caps, versioned drops, retries, and concurrent uploads; do not hold DB locks during provider latency. Coordinator acknowledged this finding and owns remediation.

### R2 — Medium: local content-addressed writes collide within one process

At inspection, `backend/app/storage.py:25` named the temporary file by PID alone. Concurrent calls for the same learner/content computed the same final and temporary paths. Both saw no final file, wrote the shared temporary path, and attempted `os.replace`; the second replacement failed because the first had removed the temporary file.

Reproduction: create a temporary `LocalStorage`, submit two same-content puts with a two-thread executor, and temporarily wrap `os.replace` with a two-party barrier. Observed one `FileNotFoundError`, one success. This can surface as a 500 for valid repeated uploads.

Required fix/retest: unique temporary file per invocation in the target directory, private permissions, atomic final replacement, and cleanup on errors. Coordinator independently raised this risk and was sent the confirmed reproduction.

### R3 — High release-configuration blocker: documented S3 credentials were ignored

At inspection, `backend/app/storage.py:45` constructed `boto3.client('s3', endpoint_url=settings.s3_endpoint_url)` with no region or credential mapping. `deploy/.env.production.example` and `scripts/production_config_check.py` required `STORAGE_REGION`, `STORAGE_ACCESS_KEY`, `STORAGE_SECRET_KEY`. Boto3's default environment provider recognizes AWS-prefixed variables, not those declared application names. An operator following the supplied template could pass configuration checks but fail S3 authentication, unless an undeclared AWS role/config happened to provide it.

Required fix/retest: map the declared variables to Boto3 arguments, or consistently document and validate canonical AWS names. A synthetic client-construction test can assert argument presence without exposing credential values. Live bucket/privacy verification remains a separate external release gate even after this code/config fix.

### R4 — Medium: material processing status displayed as a false Drive claim

`frontend/src/components/Shared.tsx:10` mapped `ready` to `common.drive`. `frontend/src/components/DesktopPanels.tsx` `RecentMaterials` passed `m.status` to this storage badge. Ready local demo sources therefore displayed “Drive” despite local Collection storage and no connected account. This is visible for the sample chapters in `docs/evidence/browser/home-1440.png`.

Required fix/retest: separate source processing readiness from provider/storage confirmation. Render Ready for processing readiness, and the actual material `storage_state` for Local/Saved to Drive. A UI test must show a ready local source without a Drive label and a genuinely confirmed mocked Drive source with its explicit confirmation. Coordinator was notified with the screenshot/source trigger.

### R5 — Medium: Collection material counts were absent from the DTO

At inspection, `backend/app/core_api.py:51`–52 `collection_dto` omitted `material_count` and `last_sync_at`. `frontend/src/components/DesktopPanels.tsx` `CollectionRow` rendered `c.material_count ?? 0`, making populated Collections appear to contain zero materials. The inspected screenshot showed sample and uploaded Collections all labeled zero. Connection DTOs similarly used `last_sync` while frontend types anticipated `last_sync_at`; consumers must align with the actual contract.

Required fix/retest: expose owned Collection counts and actual sync timestamps consistently, and validate populated/empty/foreign Collection cases. Do not invent successful sync timestamps. Coordinator confirmed count/timestamp drift and owns remediation.

## Checks that did not reveal a confirmed defect

Inspected `backend/app/auth.py`, `main.py`, `settings.py`, `db.py`, `models.py`, `jobs.py`, `worker.py`, `core_api.py`, `learning_api.py`, `sessions.py`, `review.py`, `llm.py`, `ingestion_api.py`, `ingest.py`, `storage.py`, `speech.py`, `sources/publicweb.py`, `sources/local.py`, `sources/drive.py`, `sources/captions.py`, model contracts, selected tests, deployment configuration, and frontend API/preferences/study/voice/shared/dashboard components.

- Live authentication uses opaque hashed DB sessions, explicit revocation/expiry and origin+CSRF verification on writes. Authlib OIDC tests exercised real synthetic signed ID tokens with PKCE and rejection of invalid nonce, state, issuer, audience, signature and expiry. Demo identities are rejected in production mode.
- Owned entity queries and private source-object reads checked learner scope. Selected tests exercised foreign IDs, source storage keys and exports. No tenant disclosure was found in the inspected paths; this is bounded evidence, not proof for every future route.
- Public-page DNS validation rejects private and mixed public/private results, then pins the validated address. Redirects are manually revalidated and TLS remains verified. A proxy-only environment that cannot resolve target DNS is a real operational blocker; bypassing this check for arbitrary user URLs would introduce a defect. An operator-configured proxy path needs explicit exact-host policy and demonstrated private-address/TLS enforcement, not just a blanket allowlist assumption.
- Source worker handlers map retryable `SourceError` to `RetryableJobError`, permanent errors to `NeedsAttention`. Final learning writes check leases, and provider generation/assessment call after committing the DB transaction and recheck version/state before publishing. Lease recovery tests passed. Drive external success is reconciled through stable identities/write receipts. Provider IO and crash behavior beyond these tests remain limited.
- Public session/turn responses do not include the private expected-answer JSON. Exports omit private question JSON. Citation IDs and exact source quote membership are validated; critical-concept coverage and justified reviewer evidence guard completion. Non-English offline study is explicitly unavailable rather than silently falling back to English assessment.
- Preference changes persist through authenticated `/me`; account hydration and local UI cookies are distinct mechanisms. Scope/progress are not recreated during locale switching. Voice capability results truthfully remain unverified. At inspection, generic speech endpoints lacked an owned session requirement/cumulative request cap; coordinator is adding those controls and must record the new tests. Browser speech remains browser-dependent, with typing fallback; it does not demonstrate live language coverage.
- An initial suspected calibration percentage mismatch was **withdrawn**: the reviewer initially inspected the fractional internal helper and overlooked `core_api.calibration`, which produces the percentage DTO consumed by dashboard/history. A direct synthetic correct/confidence-5 invocation returned confidence 100, accuracy 100, gap 0. No application change is requested for that false positive.

## Capability and release honesty

`docs/evidence/native-agents.json` records actual native development task spawning. Runtime planner/quizzer/reviewer prompt files do not themselves imply a native agent runs inside the deployed app. Runtime learner history, due reviews and event outbox are application DB/worker features; optional Codex memory, native scheduling and native voice require their own actual platform proof. Neither configuration files nor screenshots establish production readiness.

At inspection, `docs/capabilities.md` and `docs/build-state.json` still contained package-stage/unrun descriptions while application evidence existed. Coordinator should replace stale observations with precise passed/blocked/unrun states and finding dispositions when integration is complete. Real provider/Drive/S3/speech proof, migration/PostgreSQL validation, image build/security scans, backup/restore/rollback, full browser/accessibility coverage and authorized publication remain release-report responsibilities. This review does not approve public deployment.
