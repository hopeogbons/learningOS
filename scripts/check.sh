#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
browser=false
postgres=false
for argument in "$@"; do
  case "$argument" in --browser) browser=true ;; --postgres) postgres=true ;; *) echo "Unknown option: $argument (supported: --browser --postgres)" >&2; exit 2 ;; esac
done
if [[ "$postgres" == true ]]; then
  [[ "$DATABASE_URL" == postgresql* ]] || { echo '--postgres requires an isolated PostgreSQL DATABASE_URL.' >&2; exit 2; }
fi
(cd "$REPO_ROOT/backend" && uv run --frozen alembic upgrade head && uv run --frozen pytest -q && uv run --frozen python "$REPO_ROOT/scripts/validate_contracts.py")
python "$REPO_ROOT/scripts/test_operations.py"
python "$REPO_ROOT/scripts/check_locales.py"
(cd "$REPO_ROOT/frontend" && npm run lint && npm exec tsc -- --noEmit && npm run build)
if [[ "$browser" == true ]]; then
  (cd "$REPO_ROOT" && "${BROWSER_PYTHON:-python}" tests/e2e_smoke.py)
else
  echo 'Browser suite not requested. Run scripts/check.sh --browser with Playwright browsers installed.'
fi
echo 'Requested checks passed. Offline checks do not verify live AI, speech, Drive consent or production release gates.'
