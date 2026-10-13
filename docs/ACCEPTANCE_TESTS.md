# Acceptance tests and release levels

These are implementation tests to create/run, not checks already passed. Tests must exercise real application code; deterministic provider stubs are appropriate for offline contracts, not live connection claims. Each batch records command, working directory, exit code, executed count, passed/failed/skipped/unrun, artifact path and commit. Never count a zero-test run as validation.

## Functional cases

| ID | Action / required result | Gate |
|---|---|---|
| F01 | App+worker boot; liveness and DB-backed readiness; migration from clean DB; original Home renders | B1 |
| F02 | Ingest both original chemistry chapters+Markdown/text; real source locators resolve; tiny/no-heading/empty/encrypted cases truthful | B2 |
| F03 | CSV/XLSX preserve sheet/cell or row/column refs; bounded parsing and UTF-8 non-chemistry material | B2 |
| F04 | Select exactly five titles across two materials, Go → 0/5; unselected/late-uploaded titles never change denominator | B3 |
| F05 | Drag and keyboard reorder, reload persists; conflicting version returns 409; duplicate/foreign title IDs rejected | B3 |
| F06 | No scope → cannot start; session pinned to immutable scope despite later editing | B3/B4 |
| F07 | Before answer, expected answer/rubric absent from response and DOM; confidence required; cited teaching/question | B4 |
| F08 | Wrong+confident marks weak; correct+low-confidence follow-up; one correct sub-concept never completes broad title | B4 |
| F09 | Cited critical coverage and justified correct/confident evidence complete a title; progress 1/5=20%; uncertain verdict keeps open | B4 |
| F10 | Replayed answer/finish does not duplicate event or summary/review state; interrupted session resumes | B4/B5 |
| F11 | Retrieval skill returns 5 schema-valid recall/explain/apply questions with resolvable citations; answer separate | B5 |
| F12 | Natural or explicit finish creates private summary automatically via outbox; worker crash resumes once; synthetic evidence log sanitized | B5 |
| F13 | Two native contributor tasks/worktree quiz artifacts if supported; no content leakage, evidence of execution; fallback marked | B6 |
| F14 | Drive live folder ingest, unchanged sync no duplication, changed revision recorded; denied/revoked access handled | B7 connected |
| F15 | Public web paragraph citations; available authorized captions timestamp; unavailable captions friendly, not fabricated | B7 connected |
| F16 | SSRF, redirect to private host and oversized response rejected; source prompt injection cannot change rules | B7 |
| F17 | Clear photo matches visible source; blurry photo needs retake; image usage proven only after real vision call | B8 connected |
| F18 | Fixed-clock +0/+3 due behavior; success ladder 1→3→7→14→30→30; failure→1; stage stable on retry | B9 |
| F19 | Weak spots/calibration survive API+worker restart; IANA timezone/DST/Africa-Lagos boundaries correct | B9 |
| F20 | Three-turn voice on supported browser: transcript edit, targeted cited follow-up, saved attempt; deny mic/unsupported browser → typing | B10 connected |
| F21 | No production debug completion/date override/demo principal/fake provider; every template affordance works or clearly disabled | B11 |
| F22 | Fresh staged/release checkout frozen install, migrations, documented startup and meaningful full suite pass | B11 |

## Visual/accessibility cases

V01: 390/768/1440 Home captures against supplied baseline; blue hero, 264px sidebar, shortcuts, cards and logo remain recognizable. V02: every route mobile+desktop, 360px and 991/992 boundary, 200% zoom/long strings; no overflow or hidden required capability. V03: keyboard drawer traps/restores focus, Escape and navigation close, tabs/links have correct active state, keyboard reorder works. V04: axe/contrast/label review, 44px actions, screen-reader source/confidence/progress feedback, reduced motion. Screenshot review is recorded by file and reviewer; a screenshot existing alone is not a review.

## Production/security cases

P01: two-user ownership matrix across all routes, jobs and source objects. P02: authentication/CSRF/session revoke and expiry, secret-free bundle/logs, secure cookie and no cross-user cached page. P03: PostgreSQL migrations/concurrency/idempotency; worker lease expiry/restart and outbox recovery. P04: private object links expire; upload limits/type/parser safety; SSRF and injection checks. P05: sustained synthetic load targets in SCALABILITY with metadata vs provider metrics separated. P06: backup and restore to an isolated database/object namespace; row counts/citation hashes/review due state match. P07: release rollback rehearsal; additive migration compatibility with previous image. P08: dependency/security scan and independent Codex review findings resolved or documented. P09: actual HTTPS auth/upload/study/review functional requests after deployment, no secrets in screenshots.

## Levels and stop conditions

- **Package prepared:** source coverage, templates/schema/helpers validated; no app readiness claim. This is the state of this delivery.
- **Offline demo validated:** B0–B11 local functional/UI checks pass with fake model and sample data; connected cases marked unrun/blocked; not production ready.
- **Live hackathon workflow validated:** real model/PDF/photo, authorized Drive/web/captions, turn-based voice and durable spaced review behavior pass, appropriate platform-feature evidence captured. Unsupported optional native features use labeled fallbacks, not fabricated claims.
- **Production candidate:** all required P01–P08 plus live functional gates pass, secure environment/settings exist, images/release report reviewable. Public publication awaits user authorization if not already given.
- **Production deployed and verified:** actual deploy and P09 passed with operational monitoring; no inference from merely writing Compose files.

Required application integration failures stay blocked until tested. Optional Gmail/SDK/native-memory/native-voice enhancements may remain disabled with evidence/status; they cannot silently drop core app functionality. Failed accessibility/tenant/security/restore checks block public release even if the demo looks good.

## Revision 2 required additions to all release levels

L01–L05 in INTERNATIONALIZATION cover full catalogs/preference persistence, Arabic/other-script layout, meaningful cross-language teaching/grading/citations, actual STT/TTS and unchanged learning state. D01–D06 in DRIVE_INGESTION cover automatic root/folder provisioning/reconciliation, UI file placement, direct manual drops, saved URL snapshot and shared dedup, interrupted/revoked states, and ownership/move/delete behavior.

Offline demo can validate synthetic Drive adapter logic and catalogs/layout, but cannot claim real folder placement, direct-drop scope access or speech recognition from a fake. Live workflow release requires actual Drive proof on both paths and a real manual-drop file, plus the advertised language/speech matrix. An all-ten multilingual launch claim requires L01–L05 for all ten; if any capability is unavailable, retain its exact blocked/unverified status and do not silently drop the requested language. Existing F14 requires scoped writes plus dropped-file visibility now; F20 requires selected-language and server-fallback behavior, not merely English browser speech. Production P gates remain required. No extra batches or parallel ingestion implementation is needed; these are stronger gates in the existing batches.
