# Batch 09: Durable spaced review and persistent weak spots


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, brand #2149e0, 264px desktop sidebar, 992/1400 breakpoints, blue mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Implement exact 1/3/7/14/30-day ladder from each completion/review instant; initial +1, successful stage advancement capped at 30, failure reset +1. Duplicate event cannot advance twice. Weak-spots/knowledge map/calibration history owned and persisted in DB; use UTC storage/IANA learner timezone, explicit sample windows and gap formula. Add backend CLI python -m app.review --today +Nd and scripts/daily_review.py with fixed demo clock; prohibit live date overrides and automatic date mutation. Due jobs/sync scans claim leases and recover on restart with no duplicate dispatch.

Probe native Codex recurring automation surface if present; configure a safe synthetic audit and capture a fired run only through supported flow. No assumed CLI cron command. App scheduler remains its durable worker whether native automation exists. Native Codex memory status currently observed disabled; app cannot write learner history into it by assertion. If safe project-memory feature is usable, exercise it for developer conventions only; never store learner transcripts there. Record native/fallback distinctions.

Dashboard-specific UI: DueForReview Home keeps three mobile preview rows/four desktop plus actual total; /review displays full owned due list with original colored icons/citation/interval badges. Review uses cold recall, not teach-first disclosure. CalibrationCard matched window/sample count/weak status, Collections progress and due badges reflect DB. Test +0/+3 with a fixed starting clock, full ladder/failure/replay, timezone boundaries and API/worker restart; inspect both screen sizes.


## Done when

F18/F19 pass with durable worker/history; native automation/memory claimed only with actual evidence; due-list template preserved.

## Useful delegation

Review/scheduler contributor; native audit probe and read-only persistence verification.

## Revision 2 batch work

Persist UI/study/speech preferences and language-versioned history; switching language does not restart schedule or change completion. Localized due dates/numbers use selected locale and independent IANA timezone. Drive folder polling/write queues survive worker restart without duplication; restore checks retain source bindings/preferences.
