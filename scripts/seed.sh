#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
[[ "$APP_MODE" == demo ]] || { echo 'Synthetic seed is restricted to demo mode.' >&2; exit 2; }
cd "$REPO_ROOT/backend"
uv run --frozen python -m app.seed "$@"
