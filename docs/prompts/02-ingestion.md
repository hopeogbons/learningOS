# Batch 02: Incremental material ingestion and real citations


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, brand #2149e0, 264px desktop sidebar, 992/1400 breakpoints, blue mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Implement shared ingestion pipeline for PDF, Markdown/plain text, CSV and XLSX. Preserve immutable extracted source revisions, titled Chunks, short testable Concepts and validated Citation locator/excerpt hashes. Use headings first; schema-validated model-generated headings if necessary. A tiny section may have fewer than three concepts; never invent source text to meet counts. Concept relations capture justified prerequisites/related concepts within a Collection. All model calls go through backend/app/llm.py, using a fake provider offline and explicit server-side live adapter.

Queue ingestion through durable jobs, file/type/size/parser limits, hash/idempotency and visible needs-attention/retry statuses. Implement python -m app.ingest <file> --collection <id> from backend/ with documented module path, plus source locator resolution. Generate original chemistry Chapter 3/4 PDFs from the supplied Markdown fixtures and spreadsheet fixtures under clear licensing; add UTF-8/non-chemistry and edge cases. Live AI smoke is separate from fake tests and requires verified binding/destination.

Dashboard-specific UI: Add Material route uses existing white cards, source icons/colors and RecentMaterials row/badge treatment; a Collection picker is required. Home RecentMaterials updates from backend status/counts. Citation chips open authorized PDF-page/text/cell viewers in the same card/overlay vocabulary. Test three resolved PDF citations and sheet/cell citation, duplicate input, empty/encrypted/no-heading/oversize file; make screenshots of loading, success and attention states.


## Done when

F02/F03 and source-resolution checks pass; original licensed fixtures ingested; actual errors stay truthful; Add Material fits template.

## Useful delegation

Ingestion adapter/fixture work; separate UI status/source-viewer contribution.

## Revision 2 batch work

Add source_language and storage-origin state. UI uploads queue an owned Drive-write prerequisite before final connected ingestion success; accept staging while folder/consent is pending with clear state. Preserve original excerpt hashes under translated displays. Implement typed managed link-source snapshot contract to reuse in B7, not a second unrelated pipeline. Test cross-language fixtures and queued/confirmed write states.
