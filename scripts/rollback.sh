#!/usr/bin/env bash
# Review a previous-image rollback. Applying it is an explicitly authorized release action.
set -euo pipefail
source "$(dirname "$0")/common.sh"
[[ $# == 1 && -f "$1" ]] || { echo 'Usage: scripts/rollback.sh /absolute/private/previous-release.env' >&2; exit 2; }
env_file="$(realpath "$1")"
python "$REPO_ROOT/scripts/production_config_check.py" "$env_file"
PRODUCTION_ENV_FILE="$env_file" docker compose --env-file "$env_file" -f "$REPO_ROOT/deploy/compose.production.yml" config --quiet
echo 'Previous immutable image configuration is valid. This script changed no deployment.'
echo 'Before applying: confirm additive migrations remain compatible with this previous image and verify the latest isolated restore.'
echo 'On the approved target, run Docker Compose with that reviewed env-file and compose.production.yml: up -d --no-deps backend worker frontend edge.'
echo 'Do not downgrade/drop the database automatically. Verify HTTPS/login/upload/study/review after rollback.'
