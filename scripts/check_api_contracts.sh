#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/common.sh"
(cd "$REPO_ROOT/backend" && uv run --frozen python scripts/export_openapi.py --check)
schema_check_dir="$(mktemp -d "$LEARNING_OS_RUNTIME_DIR/api-schema-XXXXXX")"
trap 'rm -rf -- "$schema_check_dir"' EXIT
(cd "$REPO_ROOT/frontend" && npm exec --yes --package=openapi-typescript@7.10.1 -- openapi-typescript "$REPO_ROOT/contracts/openapi.json" --output "$schema_check_dir/api.generated.ts")
diff -u "$REPO_ROOT/frontend/src/lib/api.generated.ts" "$schema_check_dir/api.generated.ts"
echo 'Actual backend OpenAPI and generated TypeScript contract match.'
