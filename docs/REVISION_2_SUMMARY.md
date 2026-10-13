# Revision 2 — languages and two input paths

This revision updates the prepared orchestration package. The learning application has not been implemented yet. Source dashboard install/build/browser evidence is preserved from Revision 1; no new app feature is presented as passed.

## Already captured, now surfaced

| Requirement | Revision 1 coverage | Revision 2 action |
|---|---|---|
| Upload material from the UI | Add Material route, multipart endpoint, queued processing, source-type tabs | Retained; connected uploads now land in the correct Drive folder, not only private app storage |
| Paste web/YouTube links in UI | Add Material link tabs, public-page/captions adapters and citations | Retained; linked material now gets a managed source record/snapshot in the Collection's Drive folder |
| Material dropped directly into Drive | Folder link, manual Sync and periodic polling/dedup | Retained; bound folders auto-provision and both paths share the same source identity/pipeline |
| Automatic Drive folders | Collection row optionally held a folder ID; app-created folders not specified | Added app root and per-Collection folder provisioning/reconciliation after connection |
| Switching language | Locale field/externalized copy/UTF-8/RTL test mentioned; English remained baseline | Promoted to ten required translated UI/study languages, persistence, Arabic RTL and language-aware grading |
| Speaking other languages | Browser speech and typing; server speech optional; no ten-language requirement | Required STT/TTS capability matrix, language selection and server adapter where browser voice is missing |

## Specific launch languages

English, Chinese (Simplified), Spanish, Arabic, Portuguese, French, Japanese, Russian, German and Indonesian, in the screenshot's order. Exact native labels are in `contracts/language-registry.json`. UI language, learning-response language and speech locale are distinct preferences with sensible linked defaults. Original source quotations and citations are preserved when lessons are translated. Only exercised/reviewed language capabilities may be called supported; placeholder catalogs and a dropdown alone fail the gate.

## Collection ingestion flow

```
Connect Drive once → create/reconcile Learning OS app folder
Create Collection → create/reconcile its own Drive folder → persist folder ID

UI file upload → selected Collection → queued Drive upload → bind Drive file ID → shared ingestion
UI pasted link → permitted fetch/captions → managed link record/snapshot in Collection folder → shared ingestion
Direct folder drop → bounded change/poll scan → same bound source identity → shared ingestion
```

Uploads and sync are idempotent: scanning a file the app just uploaded must not create a second material. No false Drive-success badge while writes are queued/offline/denied. Existing folder connections are reconciled by persisted IDs/managed metadata, not names. This is two intake paths into one Collection pipeline, not arbitrary bidirectional folder deletion or editing.

## Other scalability measures retained

- PostgreSQL, tenant isolation and stateless API; independent durable workers with retry/lease recovery.
- Private object storage/source adapters and portable container deployment.
- Pagination, upload/parser quotas, token budgets and cost/latency measurement.
- IANA timezones, UTC persistence/DST handling, UTF-8 and source-language preservation.
- Text-first interaction, upload retry/status and slow-network tests.
- Synthetic load targets, backup/restore and rollback gates rather than unmeasured global-scale claims.

Use [Internationalization](INTERNATIONALIZATION.md), [Drive ingestion](DRIVE_INGESTION.md), [Scalability](SCALABILITY.md) and [Acceptance](ACCEPTANCE_TESTS.md) for details. All twelve prompts, master instructions, product/UI/API/data/privacy/deployment contracts and evidence rules now refer to this revision. Original source ZIP/PDFs remain unchanged.

## PDF/download diagnosis

The original PDF parses all 76 pages and is approximately 0.7 MB, well below the reported 40 MB limit. File corruption or size was not reproduced. This revision supplies a direct-download PDF plus a ZIP containing that PDF for clients that cannot preview it. A Markdown reading edition and the full editable ZIP remain available; no size reduction is necessary. Client connectivity/preview behavior cannot be verified from the workspace.
