#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
mode="${1:---demo}"
case "$mode" in
  --demo)
    "$REPO_ROOT/scripts/check.sh"
    docker compose -f "$REPO_ROOT/deploy/compose.demo.yml" config --quiet
    docker compose -f "$REPO_ROOT/deploy/compose.postgres-test.yml" config --quiet
    echo 'Offline release checks passed. Consult docs/RELEASE_REPORT.md for live and production blockers.'
    ;;
  --production)
    [[ $# == 2 && -f "$2" ]] || { echo 'Usage: scripts/release_check.sh --production /absolute/private/production.env' >&2; exit 2; }
    env_file="$(realpath "$2")"
    python "$REPO_ROOT/scripts/production_config_check.py" "$env_file"
    PRODUCTION_ENV_FILE="$env_file" docker compose --env-file "$env_file" -f "$REPO_ROOT/deploy/compose.production.yml" config --quiet
    echo 'Production configuration syntax/required settings passed. Live integrations, private storage policy, release tests and publication approval remain separate gates.'
    ;;
  *) echo 'Usage: scripts/release_check.sh --demo | --production /absolute/private/production.env' >&2; exit 2 ;;
esac
