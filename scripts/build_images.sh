#!/usr/bin/env bash
# Build local review images; never push, create a registry account or deploy.
set -euo pipefail
source "$(dirname "$0")/common.sh"
require_command docker
target="${1:-all}"
[[ "$target" == all || "$target" == backend || "$target" == frontend ]] || { echo 'Usage: scripts/build_images.sh [all|backend|frontend]' >&2; exit 2; }
export DOCKER_CONFIG="${DOCKER_CONFIG:-$LEARNING_OS_RUNTIME_DIR/docker-config}"
mkdir -p "$DOCKER_CONFIG"
build_args=(--progress plain)
# Docker predefined proxy args are excluded from image history. Never persist
# their values as Dockerfile ENV/ARG or print a credential-bearing proxy URL.
for variable in HTTP_PROXY HTTPS_PROXY http_proxy https_proxy NO_PROXY no_proxy; do
  if [[ -n "${!variable:-}" ]]; then build_args+=(--build-arg "$variable"); fi
done
if [[ -n "${SSL_CERT_FILE:-}" && -f "$SSL_CERT_FILE" ]]; then
  build_args+=(--secret "id=cloud_ca,src=$SSL_CERT_FILE")
fi
# A platform proxy hostname may be in this machine's hosts file but unavailable
# to the Docker build resolver. Pass only its resolved host/IP, never credentials.
while IFS= read -r host_mapping; do
  [[ -n "$host_mapping" ]] && build_args+=(--add-host "$host_mapping")
done < <(python - <<'PY'
import os,socket
from urllib.parse import urlparse
seen=set()
for name in ('HTTP_PROXY','HTTPS_PROXY','http_proxy','https_proxy'):
    host=urlparse(os.getenv(name,'')).hostname
    if not host or host in seen:
        continue
    seen.add(host)
    try:
        ip=socket.gethostbyname(host)
    except OSError:
        continue
    print(host+':'+ip)
PY
)
if [[ "${LEARNING_OS_BUILD_NETWORK:-}" == host ]]; then
  build_args+=(--network host)
fi
if [[ "$target" == all || "$target" == backend ]]; then
  docker build "${build_args[@]}" -f "$REPO_ROOT/deploy/backend.Dockerfile" -t learningos-backend:demo "$REPO_ROOT"
fi
if [[ "$target" == all || "$target" == frontend ]]; then
  docker build "${build_args[@]}" -f "$REPO_ROOT/deploy/frontend.Dockerfile" -t learningos-frontend:demo "$REPO_ROOT"
fi
echo 'Local review images built; no images were pushed and no deployment changed.'
