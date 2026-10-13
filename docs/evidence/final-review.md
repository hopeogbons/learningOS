# Final independent implementation review

Review date: 2026-10-13. Native reviewer: `/root/final_review`, independent of implementation owners. Scope: read-only source inspection, existing evidence inspection, HTTP metadata reads, and isolated regression tests. The reviewer edited only this report. This report does **not** approve production publication.

## Reviewed snapshot and executed checks

Before targeted review, 78 backend application/test and frontend source files were hashed into an untracked temporary snapshot. The SHA-256 of the serialized hash inventory was `f62125b790c2039c537c45e8b7d0c5fbd3feda39fb3ff1659322ade6f8ea211a`. At the end of the initial inspection, none of those source/test files had changed. Documentation and subsequently recorded browser evidence can change independently; a later release must identify its own final commit/artifact hashes.

Executed in `backend/`:

```text
UV_CACHE_DIR=/tmp/learningos-uv-cache uv run --frozen pytest -q \
  tests/test_sources.py tests/test_core.py tests/test_speech_owned.py
```

Result: exit 0, **59 passed**, no skipped cases, two upstream deprecation warnings, 12.75 seconds. This run exercises source extraction, source ownership, Drive adapter receipts/replay, aggregate quotas, concurrent quota/storage writes, DNS/redirect defenses, public response schemas, account locale/progress stability, Collection counts, and session-owned speech limits. Speech and Drive provider responses are synthetic adapter fixtures; these tests do not establish actual Google folder placement or audible multilingual quality.

The coordinator's separate full-suite evidence, `backend-tests.log`, reports **91 passed**, exit 0, three upstream deprecation warnings. The coordinator reports that this run enabled the isolated PostgreSQL fixture, including migration and separate-worker lease-recovery cases. This reviewer inspected that log and the test implementations but did not independently repeat the PostgreSQL full-suite run.

## Earlier finding dispositions

| Finding | Re-review disposition | Evidence and limit |
|---|---|---|
| R1: link/direct-drop quota bypass | Corrected; regression passed | UI, link-descriptor, and direct-drop persistence use the same learner-row reservation lock. Existing revision size is excluded before replacement. Concurrent SQLite reservation regression permits one four-byte source under a six-byte cap; the other fails. Live Drive behavior remains unrun. |
| R2: same-content local temporary-file race | Corrected; regression passed | Each call uses a private unique `mkstemp` file, fsync and atomic replacement, with cleanup. The formerly failing synchronized two-thread trigger passes. |
| R3: documented S3 credentials ignored | Corrected; configuration regression passed | Declared `STORAGE_REGION`, `STORAGE_ACCESS_KEY`, and `STORAGE_SECRET_KEY` map to Boto3 arguments. Omitting these retains the default AWS credential chain. Actual bucket access and private policy remain unverified. |
| R4: Ready material falsely labeled Drive | Corrected in source | Processing `ready` translates to Ready; recent materials render separate actual storage and processing badges. Existing inspected screenshot now shows Local + Ready. A fresh final browser capture remains the coordinator's responsibility. |
| R5: populated Collections displayed zero materials | Corrected; regression and fresh API read passed | Owned, nonarchived source counts and actual sync timestamps are exposed in typed DTOs. Fresh API at port 8020 returns sample `material_count=2` in both Collection and dashboard responses. Old port 8010 and the old Home screenshot still omit the field; those are stale evidence and should be superseded. |

The earlier legacy generic-speech test failure is resolved in this inspected suite. Public speech routes now require an owned active Session and current owned item. TTS accepts only persisted public teaching/question/post-answer feedback identifiers; it rejects arbitrary caller text and private answer requests. STT verifies MIME, byte size and actual audio duration, provides an editable transcript without recording an answer, and enforces the three-answered-voice-turn cap. Durable learner reservations limit request frequency and daily STT seconds/TTS characters; concurrent budget regression passes. Provider I/O occurs after reservations commit. Denied/unavailable speech remains a typed fallback, never a claimed live success.

Public response models explicitly describe core/source/learning/speech DTOs. Inspected schema tests exclude private expected answers, encrypted OAuth credentials and resumable upload URLs. This is useful contract coverage; it does not prove every future dictionary field is safe.

## Geographic scalability and language boundaries

The ten requested UI locale keys, independent UI/study/speech preferences, persistent account settings, Arabic RTL layout, local script fonts, and unchanged original citation/progress contracts are implemented and covered by local tests/evidence. The inspected Arabic mobile image mirrors the shell and retains the six actions. Original dashboard card/hero/sidebar vocabulary remains recognizable; no quantitative pixel-diff approval is implied by this visual inspection.

One concrete specification gap was sent to the coordinator during initial inspection: source-language specification/correction was missing for sources whose adapters returned `und`. The implementation owner subsequently added a learner-specified source label during file/link intake and an owned correction endpoint/control. A further independent targeted run, `uv run --frozen pytest -q tests/test_sources.py -k source_language`, passed **12 cases**, exit 0, with 32 other cases deselected and two upstream deprecation warnings. These cases check valid/invalid tags, explicit learner provenance, original content/hash/citation preservation, unchanged existing turn metadata, foreign/archive denial, actual adapter metadata, and a separate-session correction while the worker has a stale ORM cache. The worker refreshes/locks source metadata before publishing extraction and preserves a concurrent explicit learner correction. Unknown sources remain honestly `und`; automatic language detection is not claimed. Source labels need not be one of the ten UI languages. Fresh visual interaction with the added control remains coordinator-owned evidence.

All-ten generated teaching/assessment and all-ten real STT/TTS exchanges remain unrun without actual configured providers and language review. Authored translation catalogs are not human linguistic approval. Switching an interface language successfully is distinct from proving cross-language grading and spoken quality.

## Measured performance gate

`performance-postgres.json` records the actual five-minute local PostgreSQL probe: 50 synthetic authenticated learners, 5,000 titles, 50,000 concepts, two API workers, maximum 50 in-flight clients, and 20 actual initial text-ingestion jobs. It completed **35,350 requests with zero errors**, approximately **117.66 requests/second**; all 20 initial jobs succeeded once.

The required latency gate **failed**: overall p95 **855.08 ms** against **500 ms**, p99 1,335.82 ms. Every measured endpoint exceeded the p95 target. The jobs were an initial concurrent queue, not a continuously maintained 20-job load for five minutes. Authentication used real opaque DB sessions with synthetic preauthenticated learners, not a live OIDC exchange. There was no WAN, production TLS edge, live model, Drive, or speech latency. One ingestion source file changed during the probe, as the report records; do not describe it as a fully immutable final artifact benchmark.

The direct-function profile reports approximately 4–25 ms before concurrent HTTP dispatch; SQL aggregate times were approximately 2–16 ms in that profile. This difference suggests that concurrency, dispatch, connection acquisition and shared-host contention deserve instrumentation. It does **not** identify one proven bottleneck or justify increasing pool sizes without a measured repeat. Existing batched Collection/revision reads reduce earlier N+1 behavior, but the load target is still a release blocker. A useful next diagnostic is timing request queue/dispatch, connection checkout, SQL and serialization separately on a fixed build and comparable dedicated host, then repeating the full required run.

### Bounded four-worker experiment

At the coordinator's request, the reviewer added a parameterized `--api-workers` option to the isolated probe, preserving the default of two, and strengthened its gate to require all six metadata endpoints to meet their own latency/error limits. Hardware evidence now includes actual cgroup CPU quota and memory capacity. No API implementation was changed by this experiment.

Executed:

```text
backend/.venv/bin/python tests/performance_probe.py --seconds 15 \
  --api-workers 4 --output docs/evidence/performance-four-workers-smoke.json
```

The disposable PostgreSQL fixture variable was provided without printing its connection string. Dataset, 50 clients, 100 ms think time, initial 20 ingestion jobs and two source workers were unchanged. Actual cgroup capacity was four CPU cores and 32 GiB RAM, with five host-visible CPU IDs. Result: exit 1 for the failed target, **2,126 requests, zero errors**, 137.46 requests/second, p50 94.85 ms and p95 **792.86 ms**. All 20 source jobs succeeded once, observed within 16.48 seconds.

| Endpoint | Four-worker 15-second p95 ms | Under 500 ms? |
|---|---:|---|
| Dashboard | 928.35 | No |
| Collections | 830.94 | No |
| Outline | 956.14 | No |
| Progress | 681.58 | No |
| Review due | 547.55 | No |
| Search | 570.68 | No |

The short run demonstrates that doubling API workers did not clear the latency gate in this environment. It does not establish a causal throughput comparison against the earlier five-minute run: duration differs, the host is shared, and `ingestion_api.py` changed during the probe, explicitly recorded by source hashes. A full five-minute four-worker run was **not executed**, because every endpoint failed the prerequisite smoke threshold. The original failed two-worker report remains intact. Only this probe's owned random schema, temporary private files and subprocesses were stopped/removed. More worker expansion is not justified by this result; a fixed-build profile that separates queue/dispatch/DB acquisition/SQL/serialization is the next useful capacity diagnosis.

## Intake network and release boundaries

Pasted public-hostname intake now records a queued source after strict syntax checks without relying on synchronous target DNS. Actual worker fetch still rejects private/mixed DNS results, pins the validated address, revalidates redirects, verifies TLS and applies time/size limits. DNS failure produces retryable `web_dns_unavailable`; it creates no extracted source snapshot. This safely improves UI intake in the current restricted environment, but actual external fetching remains an operational proof gap where target DNS is unavailable. No SSRF/TLS bypass was observed.

The inspected dependency audit reports zero backend package advisories and zero frontend production-dependency advisories. The full frontend developer toolchain still has five high findings in the lint/glob chain (`GHSA-vfj7-8cjw-p6xm`), with no newer upstream `braces` patch observed in the recorded registry probe. Production standalone images are being verified separately and exclude the lint tooling. Package audit evidence does not establish OS/image scanning or provider policy; final image/rollback evidence belongs to the release gate.

Synthetic SQLite and PostgreSQL private-original backup/restore evidence exists, including preserved learning history and due-state content signatures. No real learner data or live S3 bucket was used. Final container flow and previous-image rollback were still pending in the inspected operations ledger. Native development delegation actually executed; custom role files, manually invoked hook helpers, unavailable scheduling, disabled native memory, and unverified native client voice must retain their distinct evidence states.

Actual learner Drive OAuth/consent, managed-folder writes/manual drops, private S3 behavior, real OIDC deployment, provider availability, all-ten speech, public domain/HTTPS and authorization to publish remain separate external release gates. The current local application is reviewable and its inspected regression suite passes. The performance target and the external connected-release gates do not permit a production-readiness claim.

## Final coordinator integration

Pending at this review snapshot: replace stale browser/API evidence with captures from the fresh service, verify the new source-language controls in that UI journey, and attach final immutable image/container/rollback results. Source-language API/worker regressions now pass; both attempted load configurations still fail the measured latency gate. The coordinator may append precise evidence and dispositions below; no pending gate should be converted to passed without the corresponding executed result.

## Coordinator final evidence append

After the independent read-only review, the final application suite passed104tests with no skips (including the additional recording-provider pending/next-turn locale regression). The clean-copy suite had already passed103checks, lint/type/build/catalog checks; application runtime code did not change for the added test. Final real browser16checks and axe22route/viewport combinations/0violations passed. Source-language UI correction and persisted revision identity were exercised. Declared static sidebar/topbar chrome comparison passed with0changed pixels in a matching unfocused capture state. Final frozen-source containers passed six checks, actual full-stack previous-image rollback and forward return; backend image private-file exclusion was probed. These are coordinator outcomes, not an expanded claim of independent reviewer execution. Required live gates and measured latency remain blocked.
