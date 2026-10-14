# Dashboard fidelity contract — applies to every prompt

**User branding update (2026-10-14):** The supplied brain/circuit mark and Andela palette supersede the reference template’s blue chrome and book logo. Preserve all six dashboard action colors, card geometry, typography and layout. The immutable reference remains historical design evidence.

**Visual source of truth:** `reference/dashboard/`. Before implementing, inspect its `src/app/page.tsx`, `layout.tsx`, `globals.css`, `src/components/*.tsx`, `src/data/dashboard.ts`, package files and screenshots in `reference/screenshots/`. Copy it to `frontend/` rather than recreating it. The archive supplies the Home screen; the other routes below are new screens to design using that shell, not existing supplied designs.

## Preserve these specifics

| Element | Exact source / rule |
|---|---|
| Colors | Andela emerald `#40c15f`, kale `#173b3f`, green black `#132128`, opal `#b0d6cd`, white `#ffffff`. General chrome, hero, links, focus and selected states use accessible green variations. Emerald is an accent; use dark greens for readable text and white-on-dark controls. |
| Type | Inter Variable font, local `@fontsource-variable/inter`; existing weights, sizes and spacing |
| Styling order | Bootstrap CSS in `layout.tsx`; Tailwind theme/utilities prefix `tw:`; handwritten CSS last; no Tailwind preflight |
| Breakpoints | Mobile <992px; desktop ≥992px; Bootstrap/Tailwind xxl 1400px; test 991 and 992 boundaries |
| Desktop shell | Fixed white 264px sidebar; `.app-main` left margin; sticky top bar; content max 1280px; 32px content side padding |
| Mobile shell | Green gradient `.hero`, flat bottom, fading `.hero::after`; 84px avatar; content max 640px with -28px overlap; bottom safe-area padding |
| Quick actions | Study blue `#2F7BEB`, Review amber `#F59E0B`, Add Material green `#22B14C`, Outline purple `#7C5CE6`, Voice red `#E5444F`, Progress teal `#14B8A6`; same six labels/order |
| Quick layout | Mobile 3×2 inside one white rounded card; desktop 3 columns then 6 at xxl; desktop status lines |
| Navigation | Desktop groups Home / Learn / Library / Insights / Account; mobile bottom Home, Collections, Study, Review; remaining pages in drawer |
| Due list | Three rows on Home mobile; fourth visible on desktop; full list at Review route; original icon/tint/citation/interval treatment |
| Desktop panels | Greeting + resume, four stats, DueForReview/Collections left, Calibration/RecentMaterials right; preserve `col-xl-7` / `col-xl-5` split |
| Cards | Existing white cards, `rounded-4`, soft shadows, source badges, spacing classes; no unrelated glass theme/dark redesign |
| Identity | `Logo.tsx`, `icon.svg`, standalone vector brain/circuit mark; transparent negative space, no enclosing square or white background; favicon derived from the same SVG; `Avatar.tsx` and local placeholder; don't download arbitrary portraits |

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
| `/add-material` | Choose Collection; upload/source tabs; file/camera/link/XLSX; status rows styled like RecentMaterials | multipart upload, jobs, links |
| `/study` | Collection/scope picker or resume; white teach/check card, citation chip, confidence control, one-question composer | sessions create/next/answer/finish |
| `/study?mode=voice` | Same Study card; Mic red accent, transcript and spoken follow-up; three-turn limit and typing | same session contract; speech adapter |
| `/review` | Full DueForReview list, collection filters, interval badges; cold retrieval rather than fresh answer exposure | due reviews and review session |
| `/progress` | CalibrationCard extended with matched window/sample count, weak spots and selected-scope progress | progress/history/weak-spots |
| `/connections` | Connection rows using source icons; real status, connect/sync/disconnect; unavailable states | providers, connect/callback/status |
| `/profile` | Learner name, IANA timezone, language preference, data export/delete; same cards/forms | profile read/update/export/delete |

## Visual verification and acceptance

Capture deterministic fixture Home screenshots at 390×844, 768×1024 and 1440×1000 matching `reference/screenshots/`. Freeze time/greeting/avatar/data; compare layout and static chrome before wiring real data. Review intentionally changed content separately from geometry. Brand/logo regions intentionally differ from the original blue/book reference; record those changes explicitly and check remaining geometry without hiding substantive UI. Pixel comparison target ≤1% changed pixels in designated static chrome using a documented threshold (initial proposal 0.2; calibrate renderer noise, record masks). Never use a broad mask over substantive UI. Update baselines only after explaining an intentional visual change. Also capture every new route at mobile and desktop.

Test 360px width, 991/992px breakpoint, 200% zoom, long collection/title labels, empty data, network failure, keyboard-only drawer and reordering. No clipped action labels, hidden required features on mobile, overlapping bottom bar, page-level horizontal overflow, browser console errors, or unreadable confidence controls. The Home may hide desktop detail panels, but their capabilities must remain reachable through routed screens. Run automated accessibility checks and manual focus/contrast review; token colors do not prove all text combinations pass WCAG.

## Revision 2: language selection and upload placement

Language chooser follows the ten ordered options/native labels in contracts/language-registry.json. Add it to the existing account/top-bar/Profile and mobile drawer, preserving green selected-state tint, cards and six quick actions. Arabic uses logical-direction shell styles/RTL while keeping original geometry; local CJK/Arabic fallback fonts, per-label bidi isolation, and long-language-label tests are mandatory. User-owned source labels stay original unless explicitly translated as aliases.

Add Material keeps the original green FilePlus2/Camera/Link icons and Collection picker; it now shows destination Collection/folder, upload/provision/write/ingest stages, actual Drive confirmation, retry and Local/Disconnected state. Paste URL is an ordinary form action here. CollectionsPanel displays Drive ready only after real folder provisioning, with Local/provisioning/attention badges; direct drops surface last-sync/new-material state. Speech controls display chosen study/speech language and actual fallback. See INTERNATIONALIZATION and DRIVE_INGESTION, not a new design system.
