# Learning OS - Home Screen Template

The home screen for Learning OS, a study partner that turns any material a learner already has into a gentle, citation-backed teach-and-check loop with automatic spaced review. Built with Next.js (App Router), React 19, Bootstrap 5.3 and Tailwind CSS 4.

Content and structure come from the Learning OS design document and build playbook.

## What each screen shows

- **Mobile (below 992px):** blue header with logo, notifications and greeting; six shortcuts; the first three titles due for review; bottom tab bar (Home, Collections, Study, Review). The menu button opens a slide-in drawer with the full menu.
- **Desktop (992px and up):** fixed sidebar with the full menu, search, a banner with a "Continue studying" card, shortcuts with a status line, four summary numbers, due-for-review list with intervals, collections with Drive status, confidence versus accuracy, and recent material by source type.

## Menu and the features behind it

| Menu | Feature in the design document |
| --- | --- |
| Home | Today at a glance: what is due, where you left off |
| Study | Teach and check in small loops, by text or voice |
| Review | Spaced review on a 1, 3, 7, 14 and 30 day ladder |
| Outline | Choose which titles count, reorder by drag and drop, track progress |
| Collections | Folder-like groupings, each optionally tied to a Google Drive folder |
| Add Material | Ingest PDFs, notes, photos, spreadsheets, web pages and YouTube links |
| Progress | Scope completion and confidence versus accuracy |
| Connections | Google Drive, Gmail, web and URL fetch (MCP) |
| Profile | Account |

The Voice shortcut opens Study in voice mode (turn-based teach-back).

## Run it

```bash
npm install
npm run dev      # http://localhost:3000
npm run build && npm start
```

## Logo

The mark is the Bootstrap Icons `book-half` glyph (MIT licence) in white on a blue tile, inlined in `src/components/Logo.tsx`. The same artwork is the favicon at `src/app/icon.svg`.

## Replacing the avatar

The avatar is a grid icon placeholder. Set `learner.avatarSrc` in `src/data/dashboard.ts` to an image URL and every avatar (mobile header, desktop banner, account chip) switches to the photo. The `Avatar` component in `src/components/Avatar.tsx` is the only place that renders it.

## How styling is split

| Tool | Used for |
| --- | --- |
| Bootstrap 5.3 | Grid, cards, list groups, progress bars, badges, offcanvas drawer, form controls |
| Tailwind CSS (prefix `tw:`) | Sizes, radii, shadows, gradients, per-breakpoint tweaks such as `tw:lg:grid-cols-3` |
| `src/app/globals.css` | Theme tokens, Bootstrap variable overrides, the mobile hero shape and a few hand-written rules |

Tailwind runs without its preflight reset, so Bootstrap's reboot stays in charge, and the `tw:` prefix keeps the two class systems from colliding. A custom `xxl` breakpoint (1400px) matches Bootstrap's.

## Structure

```
src/
  app/            layout, page, globals.css, icon.svg (favicon)
  components/     Logo, Avatar, MobileHero (client), Sidebar, DesktopTopBar, DesktopGreeting,
                  QuickActions, DueForReview, DesktopPanels, BottomNav
  data/dashboard.ts   all sample content and the menu in one typed file
```

Only `MobileHero` is a client component (it owns the drawer state). Everything else renders on the server. To use real data, replace the exports in `src/data/dashboard.ts` with fetched values.

## Accessibility

- Text meets WCAG AA contrast (4.5:1) on its background, including badges and muted text.
- One `h1` per view, landmarks for navigation and search, `aria-current` on the active menu item.
- Drawer closes on Escape, locks page scroll, and is inert while closed.
- Decorative icons are hidden from screen readers; progress bars carry labels and values.
- Motion is switched off for visitors who prefer reduced motion.
