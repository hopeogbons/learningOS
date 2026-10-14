#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
[[ "$APP_MODE" != production ]] || { echo 'Use the reviewed production Compose target for production.' >&2; exit 1; }
require_command setsid
require_command curl
require_command uv
require_command npm
require_command python
api_port="${API_PORT:-8000}"
web_port="${WEB_PORT:-3000}"
# Check both ports before migrations or service launch, so an existing server
# can never satisfy this invocation's readiness probes.
python - "$api_port" "$web_port" <<'PY'
import socket
import sys
ports = [int(value) for value in sys.argv[1:]]
if len(set(ports)) != 2 or not all(1 <= port <= 65535 for port in ports):
    raise SystemExit('API_PORT and WEB_PORT must be different valid TCP ports.')
probes = []
try:
    for port in ports:
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probes.append(probe)
        probe.bind(('127.0.0.1', port))
except OSError:
    raise SystemExit(f'Port {port} is occupied or unavailable. No services were started; choose free API_PORT and WEB_PORT.')
finally:
    for probe in probes:
        probe.close()
PY
export APP_ORIGIN="http://127.0.0.1:$web_port"
export PUBLIC_URL="$APP_ORIGIN"
export FRONTEND_URL="$APP_ORIGIN"
export LEARNING_OS_BACKEND_URL="http://127.0.0.1:$api_port"
export API_BASE_URL="$LEARNING_OS_BACKEND_URL"
export LEARNING_OS_DIST_DIR="${LEARNING_OS_DIST_DIR:-.next-dev-$web_port}"
child_pids=()
cleanup() {
  trap - EXIT INT TERM
  for owned_pid in "${child_pids[@]}"; do
    # Each process was started in a new session; never terminate by name or port.
    kill -TERM -- "-$owned_pid" 2>/dev/null || true
  done
  for owned_pid in "${child_pids[@]}"; do wait "$owned_pid" 2>/dev/null || true; done
}
trap cleanup EXIT INT TERM
(cd "$REPO_ROOT/backend" && uv run --frozen alembic upgrade head)
setsid bash -c 'cd "$1/backend"; exec uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port "$2"' _ "$REPO_ROOT" "$api_port" >"$LEARNING_OS_RUNTIME_DIR/api-$api_port.log" 2>&1 &
child_pids+=("$!")
setsid bash -c 'cd "$1/backend"; exec uv run --frozen python -m app.worker' _ "$REPO_ROOT" >"$LEARNING_OS_RUNTIME_DIR/worker-$api_port.log" 2>&1 &
child_pids+=("$!")
setsid bash -c 'cd "$1/frontend"; exec npm run dev -- --hostname 127.0.0.1 --port "$2"' _ "$REPO_ROOT" "$web_port" >"$LEARNING_OS_RUNTIME_DIR/web-$web_port.log" 2>&1 &
child_pids+=("$!")
ready=false
expected_dashboard_status=200
if [[ "$APP_MODE" == live || "$APP_MODE" == connected ]]; then
  # Readiness is public, while a connected dashboard must require sign-in.
  expected_dashboard_status=401
fi
for attempt in {1..90}; do
  for owned_pid in "${child_pids[@]}"; do kill -0 "$owned_pid" 2>/dev/null || { echo 'A service exited. Inspect private .runtime/*.log files.' >&2; exit 1; }; done
  dashboard_status="$(curl --silent --output /dev/null --write-out '%{http_code}' "http://127.0.0.1:$api_port/api/v1/dashboard" || true)"
  if curl --fail --silent "http://127.0.0.1:$api_port/api/v1/ready" >/dev/null && [[ "$dashboard_status" == "$expected_dashboard_status" ]] && curl --fail --silent "http://127.0.0.1:$web_port" >/dev/null; then ready=true; break; fi
  sleep 1
done
[[ "$ready" == true ]] || { echo 'Services did not become ready within 90 seconds.' >&2; exit 1; }
echo "Learning OS $APP_MODE ready: http://127.0.0.1:$web_port (API + durable worker + web). Ctrl-C stops only these child processes."
wait -n "${child_pids[@]}"
echo 'A service stopped; shutting down the remaining owned processes.' >&2
exit 1
