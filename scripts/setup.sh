#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
require_command node
require_command npm
require_command uv
node -e 'if(Number(process.versions.node.split(".")[0])<20){throw Error("Node 20+ required; tested with 24.19.0")}'
echo 'Installing the supplied frontend lock and frozen backend lock.'
(cd "$REPO_ROOT/frontend" && npm ci --no-audit --no-fund)
(cd "$REPO_ROOT/backend" && uv sync --frozen && uv run --frozen alembic upgrade head)
if [[ "$APP_MODE" == demo ]]; then
  (cd "$REPO_ROOT/backend" && uv run --frozen python -m app.seed)
fi
echo 'Setup complete. Start with scripts/dev.sh. Snapshots preserve files, not live processes.'
