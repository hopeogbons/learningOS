# Batch 07: Drive, public web and captions through verified adapters


## Standing instructions for this batch

Read AGENTS.md, docs/DECISIONS.md, PRODUCT_SPEC, UI_CONTRACT, ARCHITECTURE, API_CONTRACT, DATA_MODEL, ACCEPTANCE_TESTS and build-state. Use `reference/dashboard/src/app/globals.css`, the actual `src/components/`, `src/data/dashboard.ts` and baseline screenshots as visual inputs. Preserve Inter, Bootstrap-before-Tailwind `tw:`, Andela green palette from UI_CONTRACT (emerald #40c15f, kale #173b3f, green black #132128, opal #b0d6cd), 264px desktop sidebar, 992/1400 breakpoints, green mobile hero, six quick actions and mobile bottom tabs; add functionality inside that design, never a generic replacement.

Show a short plan then execute authorized reversible work. Probe current docs/help for platform-specific configuration. Use supported native subagents only with explicit file ownership; runtime roles are separate. Run meaningful tests and inspect mobile/desktop screenshots. Record exact commands/working directories/exit codes, test status/counts and artifacts in build-state/log. Native-feature files alone never prove use. Preserve user changes, secrets and tracked locks; do not reset/force-push or publish externally. Continue the next batch once its required gates pass; finish independent work around actual external blockers and report precise missing access without fake passes.



## Revision 2 requirements for this batch

Read docs/INTERNATIONALIZATION.md and docs/DRIVE_INGESTION.md. Ten screenshot languages are required translated UI/study/speech targets, with Arabic RTL and per-locale proof; preserve immutable original citations/scope/progress across language changes. Connected UI files and pasted links must land in the persisted Collection Drive folder; direct folder drops use the same identity/ingestion pipeline without duplication. No read-only-Drive write claim or unverified all-language voice claim. Use L01–L05 and D01–D06 as applicable, preserving the uploaded design and existing twelve-batch structure.

## Execute


Implement user-scoped source adapters and required connection/sync/link endpoints. Probe actual developer MCP tools and a real read-only authorized folder call; do not invent tool names/servers. Runtime Drive connector uses its own supported MCP server/authenticated route or a clearly labeled direct Drive API adapter with learner OAuth, folder boundary, encrypted credentials, checkpoint, content-version dedup and retry. Connecting the developer Codex plugin does not silently authorize deployed user access. Add bounded periodic folder polling plus manual Sync; disconnected/denied/revoked errors explicit.

Public page adapter captures canonical URL/snapshot/paragraph locators and rejects SSRF/private hosts/login/paywalls/unsafe redirects. YouTube adapter uses authorized available captions only with timestamp citations; no captions is friendly attention state, not generated content. No video-watch claim. Gmail optional read-only source UI remains disabled unless separately authorized/proven; never send emails. Contract tests exercise all adapters with stubs; required live Drive/web/captions proof waits for actual access and is never marked passed from stubs.

Dashboard-specific UI: Connections route reuses existing source icons/card/badge shapes and real status. CollectionsPanel shows Drive only after folder linkage, with pending/error status distinguishable; Add Material link tabs, RecentMaterials/citation viewers and Outline show actual imported sources. Sync action must show job progress/retry; empty/disconnected cases retain palette. Inspect mobile/desktop screenshots and run live minimal read operations when configured. Complete independent work and record precise missing OAuth/network prereq if blocked.


## Done when

F14–F16 offline contracts pass; connected gates marked only from actual live reads; source integration/SSRF states fit dashboard.

## Useful delegation

Source adapter contributor and connection/status UI contributor; MCP capability probe.

## Revision 2 batch work

Implement auto root/per-Collection folder provisioning and crash reconciliation, UI original uploads/resume, link descriptor/snapshot save, and direct-dropped-file detection. Resolve persisted folder IDs server-side. Verify live scope semantics: drive.file is not assumed to expose manually added files; disclose broader read scope if needed, keep writes to bound app-owned/selected folders. Poll an app-uploaded file without duplicate material; real manual drop, link save, same-name folders, denied/quota/restart states. Preserve one pipeline and user-owned references; no recursive reupload loops.
