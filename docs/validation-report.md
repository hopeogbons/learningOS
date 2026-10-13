# Application validation ledger

The current report is RELEASE_REPORT.md; per-batch machine state is build-state.json. Original validation/ files describe package/template preparation and are historical evidence, not claims about the deployed app.

| Gate | Current evidence | Outcome |
|---|---|---|
| Backend and PostgreSQL | evidence/backend-tests.log | 104 passed, zero skipped; three deprecation warnings |
| Fresh frozen setup/full check | evidence/fresh-install.log, fresh-checks.log, fresh-copy.json | Passed; source copy initially had no installed dependencies |
| Catalog/ICU/font contracts | evidence/locales.json | Ten locales, 261 keys each, 23,490 formats, 230 assets passed; human quality pending |
| Public API and generated TS drift | evidence/api-contracts.log | Actual schema and generated TypeScript match |
| Functional/visual browser | evidence/browser/results.json | 16 checks passed; see evidence/visual-review.md |
| Accessibility | evidence/frontend/a11y.json | Exact 22-route/viewport axe result, plus keyboard checks |
| Voice state/fallback | evidence/frontend/voice.json | Browser mocks only; live speech unverified |
| Dependency scan | evidence/dependency-audit.json | Backend/production npm zero; five dev lint findings documented |
| Containers/recovery | evidence/container-flow.json, operations-validation.json | Six final flow checks plus SQLite/PG restore and actual previous-image rollback passed |
| Sustained scale | evidence/performance-postgres.json | Failed p95 target: 855.08 ms; zero errors/35,350 requests |
| Live teaching/vision/Drive/speech/S3/HTTPS | evidence/live-preflight.json | Blocked/unrun; no provider calls made |
| Environment draft | evidence/environment-draft.json | Save status recorded; saving does not publish or prove future restoration |

No public production or global-language launch readiness claim is made. Docker disk failures were diagnosed and superseded by explicit successful reruns; connected proof and latency remain independent blockers.
