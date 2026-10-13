#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
export UV_TOOL_DIR="${UV_TOOL_DIR:-/tmp/learningos-uv-tools}"
export PIP_CACHE_DIR="${PIP_CACHE_DIR:-/tmp/learningos-pip-cache}"
mkdir -p "$LEARNING_OS_RUNTIME_DIR/security"
uvx --from pip-audit==2.9.0 pip-audit --cache-dir /tmp/learningos-pip-audit-cache --path "$REPO_ROOT/backend/.venv/lib/python3.12/site-packages" --format json --output "$LEARNING_OS_RUNTIME_DIR/security/backend-audit.json"
(cd "$REPO_ROOT/frontend" && npm audit --omit=dev --audit-level=high --json > "$LEARNING_OS_RUNTIME_DIR/security/frontend-production-audit.json")
# A complete toolchain report is retained separately; unresolved findings require triage.
set +e
(cd "$REPO_ROOT/frontend" && npm audit --json > "$LEARNING_OS_RUNTIME_DIR/security/frontend-all-audit.json")
all_status=$?
set -e
[[ "$all_status" -le 1 ]] || { echo 'Full frontend audit failed to run.' >&2; exit "$all_status"; }
python - "$LEARNING_OS_RUNTIME_DIR/security/frontend-all-audit.json" <<'PY'
import json,sys
report=json.load(open(sys.argv[1]))
if report.get('error') or not isinstance(report.get('metadata',{}).get('vulnerabilities'),dict):
    raise SystemExit('Full frontend audit did not return a valid vulnerability report.')
PY
if [[ "$all_status" == 1 ]]; then
  echo 'Production-package audits passed; full frontend toolchain findings remain for documented triage.'
else
  echo 'Backend, production frontend and full frontend dependency audits passed.'
fi
echo 'These package audits do not cover operating-system images, external service policies or unknown vulnerabilities.'
