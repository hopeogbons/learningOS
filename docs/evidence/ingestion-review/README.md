# Ingestion and deletion UI review

These captures use synthetic learner, Collection, PDF manifest and job fixtures. No learner sources or account data are included.

- `add-material-mobile-390.png` — Add Material source limits and one OCR-review page at 390×844.
- `add-material-desktop-1440.png` — same route and content at 1440×1000.
- `delete-material-modal-1440.png` — full deletion consequences and typed confirmation modal at desktop width.

The Playwright run checked the page at 390px and 1440px, found no horizontal overflow or browser console/page errors, opened the deletion modal, submitted the literal `DELETE` confirmation, and verified the API request used the material's expected version. The backend/API behavior is covered separately by deterministic pytest fixtures; these browser captures mock API responses and do not prove live Drive deletion or rendering arbitrary customer PDFs.
