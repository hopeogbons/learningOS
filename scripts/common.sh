#!/usr/bin/env bash
# Source only. Keep private runtime data outside tracked source.
set -euo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export LEARNING_OS_RUNTIME_DIR="${LEARNING_OS_RUNTIME_DIR:-$REPO_ROOT/.runtime}"
export APP_MODE="${APP_MODE:-demo}"
export APP_ORIGIN="${APP_ORIGIN:-http://127.0.0.1:3000}"
export DATABASE_URL="${DATABASE_URL:-sqlite:///$LEARNING_OS_RUNTIME_DIR/learningos.db}"
export PRIVATE_STORAGE_DIR="${PRIVATE_STORAGE_DIR:-$LEARNING_OS_RUNTIME_DIR/private}"
export PUBLIC_URL="${PUBLIC_URL:-$APP_ORIGIN}"
export FRONTEND_URL="${FRONTEND_URL:-$APP_ORIGIN}"
export UV_CACHE_DIR="${UV_CACHE_DIR:-/tmp/learningos-uv-cache}"
export NPM_CONFIG_CACHE="${NPM_CONFIG_CACHE:-/tmp/learningos-npm-cache}"
export npm_config_cache="${npm_config_cache:-$LEARNING_OS_RUNTIME_DIR/npm-cache}"
export NEXT_TELEMETRY_DISABLED=1
umask 077
mkdir -p "$LEARNING_OS_RUNTIME_DIR" "$PRIVATE_STORAGE_DIR"
require_command() { command -v "$1" >/dev/null || { echo "Required command missing: $1" >&2; exit 1; }; }
