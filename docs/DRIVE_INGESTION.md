# Drive-backed Collections: UI uploads and direct folder drops

One Collection, two entry paths, one ingestion pipeline. Connected Collections automatically acquire a folder; UI originals/links are recorded there, and manually dropped files there also become owned materials. This replaces the old read-only-Drive assumption. Google Drive is the user-visible collection source; private app storage remains bounded staging/extraction/cache/authorized viewing infrastructure, not a substitute for successful Drive writes.

## Lifecycle and folder provisioning

After the learner explicitly connects Drive through runtime OAuth, create or reconcile one private `Learning OS` root under their account. With a usable Drive connection, new Collections default to Drive-backed and each gets a child folder automatically; no manual folder setup step is required. Explicit Local mode remains available for unconnected/offline use. Existing local Collections can be enabled/migrated through a reviewed Connect/Enable action and queued mirror jobs. Demo/unconnected Collections may remain local with a visible Local/Connect Drive state; never imply a Drive folder exists without access.

Persist immutable root/folder IDs, ownership, folder mode (app-managed or explicitly linked), provisioning state and provider connection. Display names are cosmetic; duplicate/renamed Collection names don't change routing. Use appProperties with a stable app/Collection identity plus durable provisioning job/idempotency record. If folder creation succeeds but DB commit fails, search/reconcile the already created managed identity before retrying creation. Serialize provisioning per Collection; confirm existing folder access/ownership. Do not create a second root/folder on every login, refresh or worker restart. Lost/revoked/moved/deleted folder becomes needs-attention with explicit reconnect/relink guidance, never silent random replacement.

Optionally link an existing learner-selected folder after validating access; don't relocate/delete it or assume all content is app-owned. Default is the app-managed hierarchy. A linked read-only folder is labeled accordingly; UI Drive-write success is unavailable until the learner grants a compatible write path. No broad folder management, auto-deletion or file overwrite outside this contract.

## UI file route

1. Learner chooses Collection on Add Material and uploads a supported PDF/text/spreadsheet/photo. Resolve its saved folder ID server-side; never accept an arbitrary client-provided parent to route a write.
2. Validate type/size/quota and stage the private original with an idempotency/upload ID. Show queued/uploading status and retryable failures. If folder provisioning is pending, the write waits on that prerequisite.
3. Upload/resume to that Collection's Drive folder using the authorized runtime adapter. Record provider file ID, provider revision/checksum where available, original filename, upload origin and collection binding. Return final Drive-saved status only after provider confirmation and durable receipt; timeout/denied/quota/offline stays queued/attention, not fake success.
4. Hand the resulting owned source revision to the common extraction/chunk/concept/citation pipeline. Bind to the existing material/upload transaction. The next folder scan sees the same file identity/revision and updates/checks it without making a duplicate material or billing a second extraction.

## UI pasted-link route

Add Material includes Web/YouTube URL entry with Collection selected. Validate safe permitted source and fetch public text/authorized captions, retaining canonical URL, snapshot time, paragraph/timestamp locators. Save a small managed source descriptor plus immutable extracted snapshot (e.g. a typed `.learningos-source.json` receipt) in that Collection folder with origin appProperties; it is metadata/text, not a copied video or a fetch of gated content. Keep credentials/query secrets out of receipts. A changed source gets a versioned record, not a destructive overwrite of historical cited content.

The direct-folder adapter recognizes an app-created descriptor by typed metadata and binds it to the original link material; it does not re-ingest it as an unrelated JSON file or recursively fetch URLs from arbitrary learner files. Unsupported/no-captions outcomes show needs-attention and no invented snapshot. Descriptor parser validates schema and ownership; contents are untrusted study input, never runtime commands.

## Direct folder drop route

Scan only authorized linked Collection folders with provider checkpoints and bounded polling/changes API plus manual Sync. A learner dropping a supported file directly into a folder needs no second UI upload; the detected parent/file/revision maps it to the correct Collection and common ingestion job. New versions append immutable source revisions. Detect by stable file ID + provider revision within tenant/Collection, plus hash for content reuse; intentional duplicate copies are distinct source IDs unless the learner chooses merge. Same file moving to another Collection or removed from folder needs explicit reconciliation/archive state; don't delete prior scope/history or silently copy assessments.

Initial polling target: discover a new supported file within 60 seconds of an active worker's poll window (configurable), subject to provider/network limits; show last-sync time and pending state. This is a measured target, not instant/always-on detection. Google webhook/watch channel renewal is optional optimization; durable polling remains the reliable default. Unsupported shared-drive/Google-native-document export modes are disabled until separately verified, not claimed from basic binary-file tests.

## Consent and least privilege

Write permission is needed for creating app folders and UI uploads. Narrow `drive.file` can support app-created/selected files, but a folder choice alone may not grant access to arbitrary new files manually dropped there. Verify Google's current scope semantics and the real dropped-file operation. A practical documented option is `drive.file` for app-managed creation/writes plus `drive.readonly` for explicitly consented source reading, with the app restricting read operations to configured Collection folders; the broader read scope is disclosed and may require OAuth verification. Do not ask for unrestricted all-Drive write access by default or claim `drive.file` covers an untested direct-drop scenario. Picker/per-file consent is a narrower alternative only when the user experience and actual file discovery support it.

Runtime OAuth/account identity is separate from a personal Codex connector. Probe existing bindings, then use secure consent flow; never paste tokens into chat, reuse developer tokens in deployed code, or print credentials. Disconnect cancels jobs/revokes credentials; app stops writes/polling. Gmail remains optional read-only; this request doesn't authorize sending mail.

## Reliability and privacy

Folder provisioning, upload, source receipt, and extraction are distinct durable states with bounded retries/leases/quotas. Provider and DB are not one atomic transaction: reconcile external success receipts after crash. Record idempotency/origin/file revision before scheduling repeat scans; prevent upload→scan→reupload loops. Database owns app progress/history; Drive owns original/source receipts, not learner grades/transcripts. Private citation objects/Drive viewers are owner-authorized; no public sharing link or account-crossing write. Offline queued UI file remains staged locally with clear pending-Drive status; reconnect retries the same upload and reconciles scope without duplication.

## Required gates

D01: connecting/creating/retrying/restarting creates one root and one correct Collection folder; duplicate names route by IDs. D02: UI upload appears in its bound Drive folder and correct Outline; scanning it yields one material/revision. D03: direct Drive drop appears automatically in that Collection without UI upload; use a genuinely manually added file to test scope capability. D04: pasted web/captions link produces correct Drive descriptor/snapshot and citations once. D05: interrupted resumable upload/provisioning DB crash/quota/revocation keep truthful status and recover without duplication. D06: another learner/folder/Collection cannot receive or reveal a source; move/delete/rename have safe documented behavior. All D01–D06 require live provider proof for the connected release, plus offline adapter failure/replay tests. A stub response cannot establish actual folder placement or manual-drop access.
