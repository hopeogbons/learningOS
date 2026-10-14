# Operations, continuity and recovery

## Runtime

Monitor API p95/error rate, worker heartbeat and queue age, stuck/failed jobs, provider error/usage/latency, scheduled due backlog, DB/storage health, auth failures, quota rejection and backup age. Log request/job/event IDs and sanitized codes, not content. `/health` proves process life; `/ready` checks DB/migration/worker freshness and required configuration. Provider outage yields queued/retryable UI and bounded backoff; never fake a correct answer.

Daily backup schedule covers PostgreSQL, private source blobs, extraction/citation metadata and encryption-key recovery through secure key management. Define first-release RPO 24h/RTO 4h as targets; measure restore and revise before claiming them. Store encrypted off-host backups with retention and ownership. Monthly rehearsal (and before first public release) restores into an isolated namespace with no worker/email side effects and validates source/citation hashes, attempts, due state and counts. Deletion/retention policy includes backup expiry.

## Build continuation

Read `docs/build-state.json` and `docs/build-log.md` on resume, inspect Git, locate last gate/evidence, and continue earliest pending requirement. Lock dependency/tool versions and preserve valid build output. A failed check is recorded with exit status, expected vs actual, diagnosis and next action; unrelated successful checks don't erase it. Re-running a command must follow a changed condition or a specific diagnosis, not unchanged retry loops.

Use local batch tags as optional non-overwriting checkpoints after meaningful tests. Recover by a new corrective commit or revert of a scoped known change with clean review; preserve user modifications. Never instruct `git reset --hard` as normal recovery. An unborn repo has no recovery tag until an initial commit exists. Worktree cleanup only removes task-owned clean, merged worktrees after preserving artifacts and confirming no user changes; never remove the shared main checkout.

## Incidents

Source ingestion failures: preserve last valid revision, classify need-attention vs retryable, verify parser/provider limits and scope. Duplicate results: inspect idempotency/event/lease IDs, pause offending worker, correct transaction boundaries before replay. Auth/token failures: check names/status and scoped operation, prompt user for re-consent securely; don't duplicate secret declarations. Suspected ownership leak: disable affected route, revoke implicated sessions/links, preserve redacted evidence, run two-user suite and review before reopening. Production migration failure: stop release, use tested image/schema compatibility plan and isolated restore, not untested destructive downgrade.

Revision 2 monitoring adds folder provisioning/write queue age, Drive quota/consent/revocation errors, upload retries/dedup reconciliation and manual-drop scan freshness. Record speech errors/latency/quotas by capability/locale without retaining audio/transcripts in telemetry. Restore verifies Drive folder/file mappings and saved user language preferences along with citations/history; no restore job should create duplicate folders or reupload sources blindly.

## Diagnosing a failed small PDF upload

A 9 KB PDF is below the default 20 MiB intake limit; file size alone does not diagnose the failure. Record browser origin, selected Collection, request HTTP status, job state/error code and material storage state without storing private contents. A 202 response is durable intake acceptance, not extraction or Drive success. Inspect the running worker and bound folder/consent state; use `bash scripts/local.sh doctor` for connected localhost configuration checks and preserve its existing private data. `encrypted_pdf` requests an unlocked copy; `unreadable_pdf` indicates parser failure; `ocr_required` means no extractable text and requests clear page photos for the verified vision path. Do not reset/reseed the user database or substitute fake provider success to clear an error. Rebuild/restart the existing configured launcher after source changes; cloud checkout changes alone do not update an already-running user localhost image.

## Readiness after a schema upgrade (2026-10-14)

A 503 from `/api/v1/ready` is not proof that the web server failed. Inspect its sanitized dependency states. A newly upgraded database was incorrectly rejected when migration 0003 shipped but readiness still required 0002; this fixed-ID comparison has been replaced with the shipped Alembic head set. Preserve data and apply normal forward migrations; do not reset/seed/delete volumes to clear readiness. Every new migration must pass the fresh-upgrade readiness regression. CI must wait for direct and frontend-routed readiness, explicitly fail if its startup budget expires, and avoid launching E2E on an unready app. Only safe dependency-state JSON is printed on timeout; private runtime logs are not published.

When source extraction preserves hierarchical headings, browser fixtures must resolve their current full display titles and verify durable source IDs/order instead of assuming a legacy bare-heading label. This must not weaken keyboard-reorder, scope or citation assertions. Restricted cloud deployments must also provide the integrity-verified tokenizer cache used by token-window extraction; never replace exact tokenization with an unverified fallback or expose private settings to fetch its public data.

When an upload button is disabled after a source-limit API change, distinguish missing/unavailable server limits from a failed upload. Browser mocks must supply the limits endpoint explicitly, and a negative test must preserve disabled submission when those limits cannot be confirmed. Do not hardcode a permissive client limit to work around an unavailable response.
