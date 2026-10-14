# Reproducible control layout and collection language — 2026-10-14

## Problem and shared fix

Bootstrap small text-only button links had their original padding/line box plus a 44px minimum hit area, leaving extra space below the label. Icon actions already used flex alignment, producing inconsistent sibling controls. The shared `.btn` rule now centers its content on both axes, keeps 44px minimum width/height, allows natural text wrapping and prevents icon shrink. Existing per-variant/dashboard colors, focus, disabled states and input styling are preserved. Inspected collection form inputs/selects have balanced padding, comfortable 44px height and readable labels; no input redesign was necessary.

Collection cards now say **Explore collection**, describing the materials/study-section destination rather than the ambiguous View/Open outline. All ten catalogs and the source message inventory use the new wording. Internal route IDs, localization keys, selected scopes, ordering and learning history remain compatible.

## Fresh-build contract

UI_CONTRACT and PRODUCT_SPEC define the intended controls and collection wording. Foundation/release prompts require the same behavior. tests/control_layout.py runs in both GitHub CI and scripts/check.sh --browser, against the running pinned-build synthetic demo. It generates its own source/collection and restores profile preferences, archives only that collection, checks actual rendered text bounds rather than CSS declarations, wraps long labels, checks input geometry, verifies no overflow and follows the actual collection link. No manually applied runtime style patch is needed after a clean rebuild.

## Verification

- Frontend lint passed.
- Docker production frontend build passed compilation, TypeScript and 16 routes.
- `E2E_BASE_URL=http://localhost:3151 python tests/control_layout.py`: six collection cases (English/German/Arabic at 390/1440), plus home/form widths 360/390/768/991/992/1440 passed. Root inspected English mobile/desktop collection screenshots, mobile form and Arabic mobile collection; centered labels, consistent spacing and readable RTL verified.
- Ten catalogs/270 keys, 24,300 ICU formats and 230 local font assets passed.
- Six contract schemas/current build state/ten-language registry passed.
- Independent read-only review found no blockers; added explicit form visibility before measuring controls to avoid empty assertion loops.

The initial local Next production attempt was blocked by the sandbox’s subprocess socket policy; the actual Docker build succeeded. Synthetic demo checks do not prove live Google Drive or public production hosting. Existing data is preserved during the deployment to the existing cloud demo.

## Deployment verification

Published implementation commit `05f57235c27bdea1a78b69c907e76bb0859beeac` to main. Updated only the existing cloud demo frontend container, preserving backend, worker and data volume. The new frontend image became healthy. `E2E_BASE_URL=http://127.0.0.1:3150 python tests/control_layout.py` passed all six translated collection cases and six responsive form widths against that deployed production frontend build. Public hosting status remains unchanged.
