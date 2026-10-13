---
name: design-fidelity
description: Review or implement Learning OS screens while preserving the supplied dashboard and its responsive behavior.
---

# Design Fidelity


1. Read docs/UI_CONTRACT.md; inspect reference/dashboard/src/app/{page,layout,globals.css}, original components and baseline screenshots. Read installed Next.js guides before coding.
2. Identify the changed route, its API data/action and original component vocabulary. Preserve font, palette, hero/sidebar/quick actions/bottom tabs, grid, card radii and import order. Add functionality within AppShell.
3. Render deterministic Home at 390/768/1440 and changed routes mobile/desktop. Review screenshots, keyboard focus/reorder/drawer, 360px/991/992 boundaries, long text, empty/error and reduced-motion behavior. No required mobile features hidden.
4. Compare static chrome against baseline with documented masks/thresholds; explain intentional content changes. Never update baselines to hide a regression. Run accessible-name/contrast/axe and functional route checks where available.
5. Report exact screenshot files, observations, issues/fixes and actual test results. Keep private data out of artifacts. Screenshots and lint alone don't prove functioning application journeys.

Revision 2: read docs/INTERNATIONALIZATION.md and DRIVE_INGESTION.md. Verify localized output/RTL/source preservation and correct-folder UI/drop convergence when relevant; missing live proof stays blocked. All ten requested speech capabilities and actual scoped Drive writes need separate evidence.
