# Product specification

Learning OS turns a learner's own incremental material into a citation-backed teach → check → calibrated review loop. It serves independent adult learners, certification preparation and university study. Its claim is a distinctive workflow, not proof that it invented retrieval practice or that this particular application has measured educational efficacy.

## Primary journey

Home → create/open Collection (Explore collection) → Add Material → processing status → Outline → select titled sections from multiple materials → Go (create scope revision) → Study one concept → confidence before answering → Reviewer feedback → visible scope progress → spaced Review → persistent weak-spots/history. Resume returns to the same scope revision and next pending concept. Ingestion never auto-enrolls all titles.

## Learning invariants

1. A title is a Chunk with a user-facing heading. A concept is a smaller testable idea beneath it. A scope stores selected chunk IDs plus order and revision. Selected titles form 100%; unselected/late-uploaded titles do not count.
2. `percent = round(100 * completed_titles / selected_titles)`; an empty scope returns 0 with a 'Choose titles' state and cannot start a session. A title can occur once per scope. A completed title remains completed historically; later review failure flags weak/review-needed status rather than rewriting old progress events.
3. Reorder materials and titles persistently within their permitted parent; sorting uses explicit positions and stable IDs. Cross-material selection is supported; moving a title to another material is not silently allowed. Provide up/down controls and keyboard drag alternatives.
4. Teach one concept briefly from cited excerpts, then ask one recall/explain/apply check. The learner reports confidence 1–5 before feedback; do not expose the expected answer or grading rubric in public payloads until submission. Retrieval question wording must not contain the expected answer. A teaching paragraph can explain the idea: use application or later cold recall to assess transfer instead of merely copying that paragraph.
5. Reviewer returns correctness, missing/wrong parts, guessing/uncertainty signals, calibrated feedback, title decision and source-supported rationale. Server validates cited concept IDs, selected scope membership and critical-concept coverage before accepting completion. Correct confidence alone is not enough; one sub-concept must not complete a broad title. No fixed streak or three-correct shortcut. Stop retesting already demonstrated concepts.
6. Preserve uncertainty. A confident wrong answer triggers correction and weak status. A correct low-confidence answer prompts one targeted follow-up or later review. A confident justified answer can complete a narrowly scoped title when critical concepts are adequately demonstrated. Speech hesitation by itself is never evidence of low ability or guessing.
7. Confidence normalized as `(rating - 1) / 4`; assessed correctness as 0/1, unresolved uncertainty excluded from both matched aggregates. The dashboard uses mean confidence and accuracy for the same answered-attempt window, sample count, signed gap and optional Brier score. Tiny samples are labeled 'Not enough history'; never compare different windows.
8. Review starts at +1 day after completion. Successful reviews advance to 3/7/14/30 days from the current attempt; failures reset to +1 day. Use persisted UTC instants and the learner's IANA zone for 'today'. Deduplicate completion events and scheduler runs. Do not make skipping due work magically advance the ladder.

## Ingestion and provenance

PDF page/slide numbers (1-based); Markdown/text heading and line range; XLSX workbook/sheet/cell range, CSV row and column; photo filename/section and optional bounding box; web canonical URL, snapshot date and paragraph; captions video ID, start/end seconds and transcript language. Every citation points to immutable extracted source revision and quoted excerpt, not a model-invented page. Unsupported PDF OCR cases get a processing/needs-attention state and a photo/OCR adapter route. No silent guessed handwriting. Tiny sections may contain fewer than three concepts rather than fabricate 3–8.

Ingestion is asynchronous, with queued/running/succeeded/needs-attention/failed states. Content hashes/provider version IDs prevent duplicate ingest; changed files create revisions and require explicit scope update. A job failure retains the prior valid material and offers a retry. Explain unreadable, encrypted, empty, oversize, unsupported and no-captions outcomes gently. Original study fixtures must be license-clear; uploads remain private.

### Coherent retrieval and original-document verification

Prepare material before study: accept the upload, durably retain the original, extract readable source text, group related paragraphs under actual headings into bounded chunks, then expose titles for learner selection. Split large sections at paragraph/sentence boundaries; preserve source order and exact page/line/sheet/cell coordinates. Do not mix unrelated topics to satisfy a fixed chunk count or invent missing text. Model training/fine-tuning is not implied by this preparation stage.

Every study explanation, check and assessment uses excerpts from the selected immutable source revision. Citation inspection shows the original excerpt, locator and an owner-authorized download of the original document, allowing a learner to verify or dispute a claim. Keep citations valid after chunk subdivision; absence of supporting source means clarification/needs-attention, not fabricated content. Retrieval uses persisted owned chunks/concepts; latency improvements require measured evidence. Study teaches before checking; scheduled Review remains cold recall.

## Source integrations and channels

Connected Collections automatically provision/reconcile an app-managed Drive folder. UI originals and managed web/captions receipts are saved in that folder; manual drops are discovered by bounded polling/checkpoints and manual Sync through the same deduplicated ingestion pipeline. Resolve the parent folder from persisted Collection identity. Use explicitly consented scoped Drive write/read access and verify manual-drop visibility; unconnected demo/local mode is labeled. See DRIVE_INGESTION for provisioning, upload confirmation, retries, scope consent, disconnect and token deletion. MCP is used only where an actual deployed server exposes the needed listing/download tools; runtime OAuth/direct API adapter is labeled honestly otherwise. Public URLs never fetch login-only/paywalled content. Captions-only YouTube: official authorized transcript route or permitted source; unavailable captions return needs-attention, never a fabricated transcript or video-watch claim.

Photo input supports clear JPG/PNG; request a retake when unreadable. Turn-based Voice in Study shows transcript and cited follow-up, up to three total learner turns, editable text before submit and typing at any time. Microphone refusal/browser incompatibility leads to typing; stop speech when leaving the screen. Raw audio is not retained by default. Gmail read-only ingestion is optional after explicit permission; email sending/reminders and audio/video upload transcription are excluded.

## Required interface states

Every screen has initial loading, empty, ready, retryable-error and unavailable-integration behavior. Session screens also have pending generation, awaiting confidence/answer, reviewing, finished and interrupted/resumable states. Live failure cannot fall back to fabricated success. Demo data carries a visible 'Offline demo — sample material' marker. Production has no debug completion controls or unauthenticated demo principal.

Accessible names, visible focus, accessible source links, reduced motion, 44px touch controls, keyboard reordering, focus trap/restore on dialogs and mobile drawer, clear confidence labels and error announcement are required. Dashboard accessibility statements in its README are claims to audit, not a substitute for testing.

## Revision 2 international learners and collection intake

Follow [Internationalization](INTERNATIONALIZATION.md) and [Drive ingestion](DRIVE_INGESTION.md). Ten screenshot languages are required UI/study/voice targets. Persist ui_locale, study_locale and speech_locale, preserve original source language/excerpts/citations, and keep scope/progress/history unchanged when switching. Arabic root lang/dir and logical CSS mirror the supplied shell. Voice uses a verified selected-language browser/provider path, server STT/TTS fallback when browser support is missing and explicit typing on denied permission/unavailable service. No all-language speech claim without L01–L05 proof.

User-visible Collection states: Local / Connecting / Folder provisioning / Drive ready / Upload pending / Uploading / Saved to Drive / Processing / Attention / Disconnected. A successful local HTTP receipt or staged blob does not mean saved to Drive. UI and direct-drive intake converge on one owned MaterialRevision, and pasted links get a typed source snapshot in the same folder without copying videos or gated pages. D01–D06 live tests are required.
