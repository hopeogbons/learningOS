# Synthetic application session evidence

The actual acceptance journey uploaded a Markdown fixture, extracted original line citations through the durable worker, froze a selected-title scope, created a cited question and submitted an answer with confidence. Replaying the same answer key produced the same job and one history event. Finishing queued and persisted a summary automatically. Later scope editing left the earlier session pinned to its original revision.

Evidence: browser/results.json (real HTTP/browser journey), backend-tests.log (outbox/replay/coverage tests), container-flow.json (restart and previous-image rollback), operations-validation.json (history/schedule/source restoration). All use synthetic fixtures. Expected answers and full summaries stay in the private database; no raw learner answers, transcripts or OAuth credentials are copied here.

This proves the application event/worker path. It does not establish an automatic native Codex lifecycle hook.
