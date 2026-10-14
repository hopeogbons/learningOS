# Batch 05: Reusable retrieval skill and automatic session summary


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, Andela green palette from UI_CONTRACT (emerald #40c15f, kale #173b3f, green black #132128, opal #b0d6cd), 264px desktop sidebar, 992/1400 breakpoints, green mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Invoke the supplied retrieval-practice skill on an owned synthetic selected title. Produce five recall/explain/apply questions with expected answer separated and real citation refs, validate quiz-set schema, and confirm no answer leaks into public question wording. Reuse runtime question contract; do not treat creating a SKILL.md file as proof of invocation.

Finish a learning session naturally or explicitly: transaction writes a session.finished outbox event; durable worker computes private Reviewer summary exactly once and updates session summary/history. Duplicate finishes or crashed worker cannot duplicate completion/schedule effects. Write only synthetic/redacted developer evidence to docs/session-log.md; private live summaries stay in DB. Dashboard Study finished card uses existing icon, card, progress and muted-text vocabulary; Home resume/due/calibration update and no noisy exam tone.

Separately probe native Codex hooks. Current-source sample shows lifecycle Stop/SessionEnd, not a web-app study-session event. If supported, inspect optional hooks.example.toml/helper, validate normal trust configuration and activate only the reviewed bounded receipt hook using actual installed docs. Record an automatic native lifecycle receipt without bypass flags. If unavailable, mark native unverified/fallback and retain app outbox; do not claim the app summary is a native hook. Test skill output, outbox crash/replay and automatic app summary; inspect final-state screenshots.


## Done when

F11/F12 pass; sample skill output valid; private app summary automatic/retry-safe; native hook only claimed with separate proof.

## Useful delegation

Skill artifact generation and outbox integration; independent hook review.

## Revision 2 batch work

Skill questions/automatic private summaries respect study_locale; validate translated output still references the same sources and hidden answers. Outbox summary remains idempotent across language preferences and source origins; no duplicate summary on upload mirror/poll events.
