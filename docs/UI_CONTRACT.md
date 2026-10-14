# Dashboard fidelity contract — applies to every prompt

**User branding update (2026-10-14):** The supplied brain/circuit mark and Andela palette supersede the reference template’s blue chrome and book logo. The latest user-attached Home screenshot is the final mobile/desktop visual target; preserve its opal brain/circuit-pattern hero and original six colored quick actions. The immutable reference remains historical geometry/content evidence.

**Visual source of truth:** `reference/dashboard/`. Before implementing, inspect its `src/app/page.tsx`, `layout.tsx`, `globals.css`, `src/components/*.tsx`, `src/data/dashboard.ts`, package files and screenshots in `reference/screenshots/`. Copy it to `frontend/` rather than recreating it. The archive supplies the Home screen; the other routes below are new screens to design using that shell, not existing supplied designs.

## Preserve these specifics

| Element | Exact source / rule |
|---|---|
| Colors | Andela emerald `#40c15f`, kale `#173b3f`, green black `#132128`, opal `#b0d6cd`, white `#ffffff`. General chrome, hero, links, focus and selected states use accessible green variations. Emerald is an accent; use dark greens for readable text and white-on-dark controls. |
| Type | Inter Variable font, local `@fontsource-variable/inter`; existing weights, sizes and spacing |
| Styling order | Bootstrap CSS in `layout.tsx`; Tailwind theme/utilities prefix `tw:`; handwritten CSS last; no Tailwind preflight |
| Breakpoints | Mobile <992px; desktop ≥992px; Bootstrap/Tailwind xxl 1400px; test 991 and 992 boundaries |
| Desktop shell | Full-width patterned Home hero precedes the desktop row; 264px sticky sidebar begins below that hero; content occupies the adjacent main column with readable max 1280px; hero has 24px outer gutters |
| Mobile shell | Opal (`#b0d6cd`) `.hero` with a soft brain/circuit logo-mark pattern and kale text; top row menu/logo/notifications; 84px avatar; content max 640px with -28px overlap; bottom safe-area padding |
| Quick actions | Preserve the six original action colors, labels and order; use bright colored icon tiles, with no replacement monochrome treatment |
| Quick layout | Mobile 3×2 grid inside one white rounded card; icons centered above labels. Desktop uses the same icon/color vocabulary in 3 columns, expanding to 6 at xxl, with detail lines below labels |
| Navigation | Desktop groups Home / Learn / Library / Insights / Account in the left menu that starts after the hero; mobile bottom Home, Collections, Study, Review; remaining pages in drawer |
| Due list | Three rows on Home mobile; fourth visible on desktop; full list at Review route; original icon/tint/citation/interval treatment |
| Desktop panels | Greeting + resume, four stats, DueForReview/Collections left, Calibration/RecentMaterials right; preserve `col-xl-7` / `col-xl-5` split |
| Cards | Existing white cards, `rounded-4`, soft shadows, source badges, spacing classes; no unrelated glass theme/dark redesign |
| Identity | `Logo.tsx`, `icon.svg`, standalone vector brain/circuit mark; transparent negative space, no enclosing square or white background; favicon derived from the same SVG; `Avatar.tsx` and local placeholder; don't download arbitrary portraits. If the account name has not loaded, show localized “Fast Learner”; a persisted signed-in name always takes precedence. |

## Component adaptation rules

- Keep `Logo`, `Avatar`, `Sidebar`, `BottomNav`, `DesktopTopBar`, `DesktopGreeting`, `MobileHero`, `QuickActions`, `DueForReview` and panels recognizable. Extract an `AppShell` so routed screens use the same chrome. Avoid a second duplicated menu definition; route metadata replaces the template's hashes.
- `src/data/dashboard.ts` is currently sample content and Lucide component references. Split serializable backend DTOs from client-side icon metadata; never send icon functions through a server/client boundary. Pass real view-model data to existing presentational components. Do not keep hardcoded counts, arbitrary progress fills or always-active Home.
- Server Components may fetch personalized data only with a secure per-user identity; no cross-user cache. Use Client Components for drawer, reordering, session interaction and browser voice. Read installed version guides for cacheComponents/partialPrefetching before using these features. Private dashboard fetches cannot use a shared public cache.
- Replace `href="#..."` with Next Link routes, actual actions or accessible disabled states. The template notifications, search, log out and account chip are presently static affordances: make each work, hide it, or show its explicit unavailable state. No dead clickable controls in release.
- Preserve MobileHero visuals while adding a focus trap/restore, dialog semantics and route-change closing. Do not accept the current Escape behavior alone as a full accessibility pass.

## Screens and integration map

| Route | New behavior inside existing visual shell | Data/action contract |
|---|---|---|
| `/` | Exact Home composition; due rows, resume, collection stats and calibration from one snapshot | `GET /api/v1/dashboard` |
| `/collections` | Collection cards using CollectionsPanel icon/tint/badge vocabulary; create/edit/open, Drive/Local | collection list/create and collection-scoped reads |
| `/collections/[id]/outline` | Two material groups with titled checkboxes; Go, keyboard/drag ordering, sticky selected count and progress | outline, scope revision, reorder, progress |
| `/outline` | Collection picker → scoped outline, not a global unrelated syllabus | collections then outline |
| `/add-material` | Choose Collection; accessible drag/drop and browse; file/source tabs; camera/link/spreadsheet; effective configured file cap plus per-format page/cell limits, per-file extraction/attention status, 40-page PDF batch progress and a page-review route showing original page + extracted text for correction; material Delete action with full-consequences modal | upload-limits API, multipart upload, parser jobs, links, page-manifest/review APIs, confirmed material deletion |
| `/materials/[id]/review` | Paginated page manifest for a processing/needs-attention PDF; show original page, chapter path, extraction method, status/warning and editable transcription; resume final indexing when all nonblank pages are accepted | owner-scoped manifest/read/correction APIs; immutable original bytes |
| `/study` | Collection/scope picker or resume; white teach/check card, citation chip, confidence control, one-question composer | sessions create/next/answer/finish |
| `/study?mode=voice` | Same Study card; guided two-way tutor conversation; speak cited teaching/question/feedback, record an editable learner transcript, confidence before submit, replay/stop and typing; three voice-answer limit | same session contract; session-owned speech adapter |
| `/review` | Full DueForReview list, collection filters, interval badges; cold retrieval rather than fresh answer exposure | due reviews and review session |
| `/progress` | CalibrationCard extended with matched window/sample count, weak spots and selected-scope progress | progress/history/weak-spots |
| `/connections` | Connection rows using source icons; real status, connect/sync/disconnect; unavailable states | providers, connect/callback/status |
| `/profile` | Learner name, IANA timezone, language preference, data export/delete; same cards/forms | profile read/update/export/delete |

## Sign-in providers

The current configured identity provider is Google OIDC. The active authentication action must say **Continue with Google** (localized) and clearly refer to a Google account. Do not call this Gmail access: Gmail remains a separate, optional read-only content connection. Apple, Microsoft and other future providers may appear as clearly disabled outline placeholders labeled **Coming soon**; placeholders must not navigate, submit to Google or imply configured sign-in support. The active Google action remains filled kale; Log out remains outline/link-style.

## Visual verification and acceptance

Capture deterministic fixture Home screenshots at 390×844, 768×1024 and 1440×1000 matching `reference/screenshots/`. Freeze time/greeting/avatar/data; compare layout and static chrome before wiring real data. Review intentionally changed content separately from geometry. Brand/logo regions intentionally differ from the original blue/book reference; record those changes explicitly and check remaining geometry without hiding substantive UI. Pixel comparison target ≤1% changed pixels in designated static chrome using a documented threshold (initial proposal 0.2; calibrate renderer noise, record masks). Never use a broad mask over substantive UI. Update baselines only after explaining an intentional visual change. Also capture every new route at mobile and desktop.

Test 360px width, 991/992px breakpoint, 200% zoom, long collection/title labels, empty data, network failure, keyboard-only drawer and reordering. No clipped action labels, hidden required features on mobile, overlapping bottom bar, page-level horizontal overflow, browser console errors, or unreadable confidence controls. The Home may hide desktop detail panels, but their capabilities must remain reachable through routed screens. Run automated accessibility checks and manual focus/contrast review; token colors do not prove all text combinations pass WCAG.

## Revision 2: language selection and upload placement

Language chooser follows the ten ordered options/native labels in contracts/language-registry.json. Add it to the existing account/top-bar/Profile and mobile drawer, preserving green selected-state tint, cards and six quick actions. Arabic uses logical-direction shell styles/RTL while keeping original geometry; local CJK/Arabic fallback fonts, per-label bidi isolation, and long-language-label tests are mandatory. User-owned source labels stay original unless explicitly translated as aliases.

Add Material keeps the original green FilePlus2/Camera/Link icons and Collection picker; it now shows destination Collection/folder, upload/provision/write/ingest stages, actual Drive confirmation, retry and Local/Disconnected state. Paste URL is an ordinary form action here. CollectionsPanel displays Drive ready only after real folder provisioning, with Local/provisioning/attention badges; direct drops surface last-sync/new-material state. Speech controls display chosen study/speech language and actual fallback. See INTERNATIONALIZATION and DRIVE_INGESTION, not a new design system.

## Controls and collection language (2026-10-14)

Collection cards use **Explore collection** for the action that opens a collection’s materials, titled study sections and selection controls. The phrase replaces View/Open outline in this action across all ten catalogs. Keep the existing internal outline route and localization identifier compatible; this copy change does not alter scope selection, ordering or learning history. The Outline navigation/quick action can retain its established name when referring specifically to choosing study sections.

Shared button controls must center their text and icons vertically and horizontally within the complete hit area, including 44px minimum-height small buttons. Increasing min-height alone must not leave the text on its original top baseline. Use the shared button rule, with balanced padding and explicit alignment; preserve per-variant colors, disabled/busy/focus states, icon spacing and responsive wrapping. Inputs/selects use consistent comfortable sizing and readable vertically balanced text; multiline textareas retain natural writing alignment. Do not apply button layout rules to unrelated navigation tiles or form labels.

Sign-in is the filled kale primary action. Log out remains an outline/link-style secondary action in the mobile drawer, desktop navigation and Logout screen; never restyle it as a filled primary button.

Reproduce from a clean installation with the existing pinned setup, backend checks, catalog check, frontend lint/build and running-app browser checks. Run `E2E_BASE_URL=<isolated-demo-origin> python tests/control_layout.py` to verify button geometry, input sizing and the Explore collection journey at mobile/desktop widths. CI executes this check against a fresh synthetic demo. Inspect screenshots for these routes and long/RTL labels after control changes. Colors, focus and source/progress semantics remain governed by this contract.

## Aesthetic refinement (2026-10-14)

- Use a softly tinted `#f3f8f6` main canvas so white cards remain distinct; use white (`#ffffff`) and opal (`#b0d6cd`) generously on cards and hero surfaces. Kale (`#173b3f`) is the primary button, selected-navigation and readable-text color. Reserve green-black (`#132128`) for small high-emphasis details/interaction states.
- The attached mobile Home is the final visual reference. Use its light opal hero surface, dark Kale text, menu/logo/notification row, avatar/name/count greeting and faint repeating brain/circuit mark pattern. Build the pattern from the standalone transparent LogoMark, placed asymmetrically with varied size/rotation/opacity and no visible rows, columns or regular grid; do not substitute Bootstrap glyphs or the full Learning OS wordmark. Preserve the mobile Home's layered hero-to-action-card relationship.
- Do not render a decorative vertical “Learning OS” wordmark or watermark anywhere in the viewport. Keep the standalone logo in its established shell position.
- Primary buttons, outline-primary controls and selected navigation use kale (`#173b3f`) with readable white text and accessible hover/disabled/focus states. The connected sign-in alert uses a pale opal treatment rather than Bootstrap blue.
- Quick actions use the original six colors from `data/dashboard.ts`. Keep icon above label in the same white rounded card; mobile uses 3 columns × 2 rows, desktop uses the same tile design in 3 columns and expands to 6 at xxl.
- Preserve the current mobile footer navigation exactly: the four tabs stay Home, Collections, Study and Review, with their existing home, folder, open-book and repeat icons, labels, active state and ordering.
- Desktop Home uses the same opal/patterned hero style as mobile, expanded into a wide greeting/resume banner with 24px viewport-side gutters. Put the desktop logo/control row and greeting/resume content inside this header. Place the desktop sidebar and content row beneath the entire banner; the sidebar begins at the banner's bottom rather than at the top of the viewport. Keep its 264px width and sticky behavior while scrolling. The desktop top bar/search and content remain in the main column beside it.
- Keep one permanent informational Home card below the hero/desktop top bar and above Quick Actions, including when signed out. Give it a small 16px top gap on desktop; on mobile retain the card's layered overlap with the hero and its internal padding. This card explains Learning OS and never acts as an authentication prompt. The lower sign-in callout in the Due for Review area remains the sign-in request; do not duplicate sign-in prompts in the upper card.
- Material deletion is a destructive, owner-scoped action. Show a modal that lists all affected Learning OS data and the connected Drive original before the final confirmation. The operation must not report completion until authorized Drive deletion and private-source cleanup are confirmed; on provider failure preserve the material/data and show an actionable retry/attention state. Explain backup-retention limits honestly.
- The mobile navigation drawer spans the full viewport width. Keep its existing focus trap, Escape behavior, route-close behavior and logo/header relationship.
- Desktop account chip places the learner name before a circular avatar placeholder with a small decorative camera badge. It links to Profile; it does not imply photo-upload functionality.

## Learning parser and spoken Study additions

CustomerSupport's document parser is a behavior reference, not a replacement UI framework. Reproduce its 160-token/20-overlap sentence-aware split behavior with OpenAI `tiktoken` and local format adapters. The actual source heading/page remains the selectable Chunk; bounded teaching/Concept windows do not create extra scope titles. Preserve source citation text/locators and keep overlapping context from duplicating assessment. HTML upload stays unsupported; public URL intake remains separately guarded. DOCX/RST/CSV/TSV/XLSX/JSON/YAML/log parsing and scanned-PDF OCR appear only with truthful parser/provider status.

Voice mode is explicitly two-way. Before starting, tell the learner the tutor can speak cited material/questions and Reviewer feedback, and the learner can reply aloud or type. During the turn show per-message listen/replay controls, visible stop, mic/stop, editable transcript, confidence and the same citations as text Study. Never advertise spoken support beyond verified browser/provider locales. Use the existing shell, card and accent vocabulary; do not copy the CustomerSupport MUI layout.

## Latest core-demo conversation interface

Use the single conversational screen specified in CONVERSATION_EXPERIENCE.md for Text, Voice note and Live voice. Entry context chooses its active mode, with typed fallback in all modes. Teacher/learner/feedback messages, composer and concise confidence controls are uniform; source evidence is an optional Source/View original disclosure. Do not label serial recording as realtime or expose expected answers/internal citation IDs as chat text. Its Done when criteria supersede old separate Voice card instructions.
