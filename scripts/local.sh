#!/usr/bin/env bash
# Connected localhost launcher; preserve private settings and all user data.
set -euo pipefail
repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
action="${1:-start}"
compose=(docker compose -f deploy/compose.connected-local.yml)
case "$action" in
  init)
    "${compose[@]}" --profile init run --build --rm --no-deps --user "$(id -u):$(id -g)" init
    ;;
  doctor)
    "${compose[@]}" ps -a
    "${compose[@]}" --profile diagnose run --build --rm --no-deps diagnose
    ;;
  start)
    if [[ ! -f .runtime/localhost/localhost.env ]]; then
      "$0" init
      echo 'Fill .runtime/localhost/localhost.env privately, then run scripts/local.sh start again.'
      exit 1
    fi
    "${compose[@]}" --profile diagnose run --build --rm --no-deps diagnose
    docker compose -f deploy/compose.demo.yml down
    "${compose[@]}" up --build -d --wait
    echo 'Connected app started with your configured browser origin. No sample data was seeded.'
    ;;
  stop) "${compose[@]}" down ;;
  *) echo 'Usage: scripts/local.sh [init|doctor|start|stop]' >&2; exit 2 ;;
esac
