# Traceability: nothing generic or silently omitted

| Source requirement | Planned batch / contract | Proof |
|---|---|---|
| Design §1–3: retrieval, teach/check, calibration | B4; PRODUCT_SPEC learning invariants | F07–F10 |
| Design §4: PDFs, notes, spreadsheets | B2; citation schema and parser contracts | F02/F03 |
| Design §4: photos | B8 | F17 |
| Design §4: public pages/captions | B7; SECURITY SSRF | F15/F16 |
| Design §4: precise source pointers/knowledge map | B2/B4/B9; MaterialRevision/Citation/ConceptRelation | citation resolution and weak-spots evidence |
| Design §5: user-created Collections | B1/B3/B7 | collection/outline flows |
| Design §6: incremental Drive; Gmail mentioned | B7 required Drive, optional authorized read-only Gmail | F14, separate optional capability status |
| Design §7: all nine Codex families | B0/B4–B10; CODEX_USAGE_PLAN | native/fallback ledger and actual artifacts |
| Design §8: text, photo input, source viewer, turn-based voice | B4/B8/B10 | F07/F17/F20 |
| Design §9: end-to-end gentle loop | B11 | complete browser journey + live gate |
| Design §10: title selection/reorder/Reviewer completion | B3/B4; scope snapshots and coverage guard | F04–F10 |
| Original playbook 0–11 and model adapter | Revised B0–B11; backend/app/llm.py | all batch gates |
| Original AGENTS, capabilities, role TOML, skill, session log | supplied repo overlay + developer/runtime separation | schema/helper validation + future actual invocations |
| Original parallel quiz sets/worktrees | B6; synthetic fixtures only | F13 |
| Original CLI ingest/review/daily script | B2/B9 generated tools, demo clock restricted | F02/F18/F19 |
| Original README/fresh-clone/scorecard | B11; release readiness and rubric evidence | F22/P01–P09 |
| Dashboard colors/font/grid/hero/sidebar/nav/cards | Every batch; UI_CONTRACT; preserved reference code | V01–V04 |
| Dashboard static controls/data become functional | B1/B3/B11; API routes and typed DTOs | F21 + routed click checks |
| User: one orchestration delivery/no repeated prompts | EXECUTE + state + full prompts | staging/resume package checks |
| User: uniqueness/scalability/Codex | RUBRIC_EVIDENCE + SCALABILITY | tangible behavior + load/native evidence |
| User: concept through production | architecture/auth/privacy/CI/deploy/ops added to B11 | production gates; explicit external handoffs |

Original design's learning-study/percentile statistic is not repeated as a project result; its research citation was not supplied/verified. The package does not assert a 99% confidence number or guarantee a production app before implementation. UI screenshots come from the real supplied dashboard; only Home was supplied and all other screens are extensions within its design language.

## User revision coverage

| Request | Updated source of truth | Batches / proof |
|---|---|---|
| Language menu from screenshot, ten languages | INTERNATIONALIZATION + language-registry.json | B1/B4/B10/B11; L01–L05 |
| Other clients can study/speak in their language | Separate persisted UI/study/speech locale, multilingual model/voice contracts | B4/B9/B10; real per-locale semantic and speech checks |
| UI uploads land in correct Collection Drive folder | DRIVE_INGESTION folder provisioning/write receipt | B1/B2/B7/B8; D01/D02/D05/D06 |
| Direct Drive dumps also ingested | Same source identity/checkpointed folder discovery | B7; D03/D05/D06 |
| Paste web/captions links from UI | Managed descriptor/snapshot + same ingestion | B2/B7; D04 |
| Surface existing scalability measures; avoid duplicates | REVISION_2_SUMMARY/SCALABILITY/RUBRIC_EVIDENCE | Existing twelve batches retained |
| PDF opens/downloads | Validated PDF + direct-download/PDF-only ZIP/Markdown alternate | Package validation, not app test |
