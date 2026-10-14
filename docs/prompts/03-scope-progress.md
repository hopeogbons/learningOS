# Batch 03: Cross-material scope, ordering and progress


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, Andela green palette from UI_CONTRACT (emerald #40c15f, kale #173b3f, green black #132128, opal #b0d6cd), 264px desktop sidebar, 992/1400 breakpoints, green mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Implement outline/scope/reorder/progress routes exactly as API_CONTRACT. Selection creates immutable ScopeRevision/ScopeItem rows, not a global Chunk boolean. Selected titles define total; zero selection cannot start; late ingestion never grows an existing denominator; sessions later bind to snapshots. Reorder uses complete sibling ID lists, expected version, ownership checks and transactional stable ordering; wrong parent/foreign/duplicate IDs fail. Scope changes create a new revision with explicit learner action.

Dashboard-specific UI: /collections/[id]/outline and /outline Collection picker inside existing AppShell. Two material groups side by side when wide, stacked when narrow, using same rounded white cards/purple Outline accent. Titled checkboxes, selected-count chip, Go in the accessible green brand palette, x of y (z%) progress with accessible labels. Allow React-safe drag interaction and keyboard/up/down alternatives; no new vanilla standalone HTML or competing design system. Home resume and CollectionsPanel reflect actual active-scope counts. Mobile Outline remains reachable through drawer/quick action.

Verify five titles across both chapters → 0/5; new material leaves 5 denominator; reorder survives reload, conflict returns 409; separate scope version does not mutate history. Completion simulation belongs only in test fixtures, never a user-visible debug button. Run frontend functional and backend progress tests and inspect mobile/desktop screenshots.


## Done when

F04–F06 pass with persistent keyboard/drag order, safe version conflicts and correct 0/5 math; no production debug control.

## Useful delegation

Scope/database contributor and React interaction contributor with shared contract; fidelity reviewer.

## Revision 2 batch work

Translate all outline/Go/order/progress messages. Verify RTL/keyboard reorder and locale switch do not change selected IDs, denominator, session scope or source order. Destination Collection/folder shown without routing by translated display names. Late direct-drop/UI material never changes an existing scope automatically.
