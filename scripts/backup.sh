#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
cd "$REPO_ROOT/backend"
uv run --frozen python "$REPO_ROOT/scripts/backup.py" backup "$@"
