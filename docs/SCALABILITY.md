# Scalability across users and geographies

Start with a modular monolith and one durable worker. SQLite is a local demonstration convenience. Production PostgreSQL supports shared state, concurrent jobs and multiple API/worker replicas without moving learning state into process memory.

| Concern | Design and evidence to generate |
|---|---|
| Horizontal growth | Stateless API; PostgreSQL sessions/jobs; per-job leases; object storage; kill/restart worker test with no lost/duplicated results |
| Geographic portability | Docker deployment with external services; configurable provider region/endpoint; ten UI/study/speech launch locales with per-language proof; IANA zone; source UTF-8/Arabic RTL; reviewed catalogs/voice matrix |
| Bandwidth/access | Cached static assets/local bundled fonts, text-first study, bounded JSON and pagination, lazy PDF page viewer; explicit upload progress/retry and pending status on slow links |
| Time correctness | UTC persisted instants; learner-zone due display; DST and Africa/Lagos tests; scheduled scans pick all due entries idempotently |
| Multiple learners | Every query/object/job owner checked; two-user isolation suite; OIDC; server-only tokens; no shared per-user page cache |
| Provider access/cost | Provider adapters, structured output validation, bounded excerpts/tokens, per-user and global quotas, timeouts, usage ledger; benchmark cost per ingest/session/review |
| Large collections | Immutable source revisions, lazy outline pages, cursor indexes, cached extraction by owned version; query-count/N+1 checks and migration rehearsal |
| Shared source differences | Locale-aware headings and source locator format; document language on concepts; no assumption of chemistry-only material |

## Initial measurable targets, not achieved claims

Record hardware, commit, dataset, warm-up, client count, network and provider mode with all results. Targets for the first production candidate: 50 concurrent authenticated learners, 5,000 titled sections and 50,000 concepts, 20 active source jobs; metadata endpoints p95 <500ms and error rate <1% under a five-minute sustained run. Model generation jobs are asynchronous: measure queue wait and provider latency separately instead of pretending they meet metadata latency. Seed data is synthetic and deterministic; load tests cannot use real learner content.

Throttle CPU-bound parsing separately from model calls; begin with API 2 workers and durable worker concurrency 2, adjusted from observed RAM/CPU and provider limits. Limit file upload 20MiB, PDF 100 pages, XLSX 10,000 parsed cells and text 2MiB by default; configurable and surfaced in UI. Tests cover exceeded limits and no unbounded retries. SSE is optional; initial bounded job polling suffices.

Slow network acceptance: test 1Mbps / 300ms latency, actionable UI remains responsive, queued processing does not freeze navigation, upload interruption offers retry and doesn't duplicate a material. Metadata cache/offline drafting is an enhancement with privacy review; full offline AI is not claimed. Regions, data residency and speech availability are documented by chosen provider; do not market unsupported countries/languages.

## Migration and scaling trigger

PostgreSQL is required before any multi-replica release. Generate SQLite→PostgreSQL export/import tooling only if real local learner data must migrate; verify row counts, IDs, source citations and history. Load failure gets a measured diagnosis and improvement (index, query batching, bounded worker concurrency) before infrastructure expansion. Add a broker or service split only after the database queue bottleneck is measured; record the decision and migration cost.

## Promoted geographic-reach gates

Ten screenshot languages are required interface, learning and speech targets, not merely a future translation-ready architecture. See INTERNATIONALIZATION L01–L05: Arabic RTL, script fonts, persisted preferences, cross-language grading/citations, real speech capability and failure fallback. Geography evidence combines them with the already required tenant/job/PostgreSQL, low-bandwidth, time/DST, quotas/load and backup tests. Language availability is separate from the chosen provider's regional availability/data residency; don't infer either from translation.

Drive UI/drop ingestion adds provider quotas, resumable uploads, checkpointed scans and write receipts. Folder discovery target ≤60 seconds of active polling and upload→scan dedup are measured with recorded provider/network conditions. Idempotent external-resource reconciliation prevents storage/API cost multiplying on worker restarts. Original UI baseline remains English for comparable pixel checks; each localized layout has additional reviewed screenshots.
