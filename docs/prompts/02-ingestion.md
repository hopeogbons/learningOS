# Batch 02: Incremental material ingestion and real citations


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, Andela green palette from UI_CONTRACT (emerald #40c15f, kale #173b3f, green black #132128, opal #b0d6cd), 264px desktop sidebar, 992/1400 breakpoints, green mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Implement the format-aware `source-excerpts-v3` parser specified in PRODUCT_SPEC.md. Use the CustomerSupport parser as a behavior reference: OpenAI `tiktoken`, 160-token sentence-aware teaching windows with 20-token overlap, format-native structure, deterministic locators and actionable unreadable-file outcomes. Keep the existing app provider boundary and Codex development workflow; do not add a second agent/model runtime. Preserve learner-selected titled Chunks as the scope denominator; windows become Concepts underneath a title, and overlap is teaching context rather than duplicate assessed progress. Support PDF, Markdown/text, DOCX, RST, CSV/TSV, XLSX, JSON/YAML, logs and photos only with exact source locator/excerpt mapping. HTML files remain excluded. Preserve immutable extracted source revisions and bytes; citations must quote exact original extracted source text and pass locator/hash validation. Never mix unrelated source regions or invent content. A tiny section may have fewer than three concepts. Generated context cannot become citation evidence. All external model calls go through backend/app/llm.py, using a fake provider offline and explicit server-side live adapter.

Queue ingestion through durable jobs, file/type/size/parser limits, hash/idempotency and visible needs-attention/retry statuses. Implement python -m app.ingest <file> --collection <id> from backend/ with documented module path, plus source locator resolution. Generate original chemistry Chapter 3/4 PDFs from the supplied Markdown fixtures and spreadsheet fixtures under clear licensing; add UTF-8/non-chemistry and edge cases. Live AI smoke is separate from fake tests and requires verified binding/destination.

Dashboard-specific UI: Add Material route uses existing white cards, source icons/colors and RecentMaterials row/badge treatment; a Collection picker is required. Adapt the reference project's accessible drag/drop affordance, supported-format chips, per-file processing/attention states and section-count summary inside the existing Learning OS shell, not its MUI design system. Home RecentMaterials updates from backend status/counts. Citation chips open authorized PDF-page/text/cell/heading/key-path viewers in the same card/overlay vocabulary. Test DOCX/RST/JSON/YAML/TSV parsing, 160/20 token boundaries, exact offsets, three resolved PDF citations and sheet/cell citation, duplicate input, empty/encrypted/no-heading/oversize files and scan OCR limits; make screenshots of loading, success and attention states.


## Done when

F02/F03 and source-resolution checks pass; original licensed fixtures ingested; actual errors stay truthful; Add Material fits template. PDF finalization must retain a durable completion marker after temporary batch cleanup: replay after a worker restart, including a crash before the queue records success, returns ready without re-extracting, duplicating teaching rows or losing original bytes. Verify this in the real-PDF multipart integration gate. Material deletion must likewise retain its durable database-deleted marker after cleanup in both completion paths; replay after worker restart must succeed without looking up removed rows or repeating remote deletes. Extend the existing comprehensive deletion gate rather than adding redundant tests.

## Useful delegation

Ingestion adapter/fixture work; separate UI status/source-viewer contribution.

## Revision 2 batch work

Add source_language and storage-origin state. UI uploads queue an owned Drive-write prerequisite before final connected ingestion success; accept staging while folder/consent is pending with clear state. Preserve original excerpt hashes under translated displays. Implement typed managed link-source snapshot contract to reuse in B7, not a second unrelated pipeline. Test cross-language fixtures and queued/confirmed write states.

## Source chunk preparation update (2026-10-14)

The prior `source-excerpts-v2` behavior remains immutable for existing revisions. New `source-excerpts-v3` uses 160-token sentence-aware teaching windows with 20-token context overlap beneath actual source titles. The 20-token overlap supports context only; it does not create a second selected title or duplicate progress requirement. Preserve original page/heading/line/sheet/cell/key-path locators and exact excerpt hashes. Reprocessing is an explicit new revision/scope action; never rewrite old citations/history. Original bytes remain privately retained and owner-authorized citation downloads return the original, not a chunk substitute. Preparation precedes Study; no fine-tuning or measured latency claim is implied.

## Latest core-demo acceptance — supersedes older communication scope

Read docs/CONVERSATION_EXPERIENCE.md before implementation. Its one-interface Text/Voice note/Live voice workflow and Done when gates govern this batch. Study selects text; Voice selects genuine realtime; voice-note selects record/send. Preserve session, scope, transcript and draft when switching. Source evidence is an unobtrusive disclosure, while internal grounding and confidence-controlled assessment remain mandatory. Only key PDF, mode-entry/persistence, speech ownership and actual provider tests are required for this demo iteration.
