# Batch 04: Cited teach/check with confidence-aware Reviewer


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, brand #2149e0, 264px desktop sidebar, 992/1400 breakpoints, blue mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Use shared runtime Planner/Quizzer/Reviewer role specifications through app/llm.py. Native Codex custom-agent TOML files are developer roles, not automatically callable by the web app. Validate schema/config and exercise available developer subagents on fixture tasks; record native proof separately. Planner selects within locked scope/order with weak-first only as a tie-break; Quizzer teaches one cited concept then poses one question; Reviewer assesses correct/partial/uncertain, missing evidence, confidence and guessing with a justified completion decision.

Implement durable session/current-item generation, idempotent answer/advance/finish and protected public DTOs. GET next reads persisted state and doesn't regenerate/consume turns. Expected answers/rubrics never exposed before submit. Server guards title completion using actual critical-concept coverage and cited evidence, not a single correct sub-concept, fixed count or confidence shortcut. Confidence 1–5 is collected before feedback; uncertain grading remains open. Preserve calibration window/sample count and private transcript/answer data.

Dashboard-specific UI: Study page is the same white card shell, Study blue icon, citation chip, short teaching, one question, accessible confidence selector, answer composer, targeted feedback and progress. Resume opens bound Collection/scope/session, not a hash. CalibrationCard/StatsRow/CollectionsPanel update after accepted assessment from a consistent snapshot. Test confident-wrong, correct-uncertain, broad-title coverage, narrowly justified completion to 1/5, injected source instructions and duplicate submission. Inspect mobile/desktop screenshots and meaningful offline suite; live model behavior remains a separate gate.


## Done when

F07–F10 pass; evidence-based completion/progress correct; answers private; native-vs-runtime distinction recorded.

## Useful delegation

Native developer Planner/Quizzer/Reviewer exercised if supported; implementation tasks divided by runtime/UI files.

## Revision 2 batch work

Runtime Planner/Quizzer/Reviewer receive study_locale/source_language and preserve source citations; semantically assess cross-language answers instead of English keyword matching. Keep formula/code tokens and original quotations intact. Freeze language for a pending item and apply changes at next turn without losing answer/history. Build per-language evaluation fixture gates and uncertainty behavior.
