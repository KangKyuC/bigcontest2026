#!/usr/bin/env bash
# Explicit deployment helper; requires an existing Vercel login.
set -euo pipefail
REPO_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/../.." && pwd)"
cd -- "$REPO_ROOT"
: "${VERCEL_ORG_ID:?Set the Vercel organization ID in your environment}"
: "${VERCEL_PROJECT_ID:?Set the Vercel project ID in your environment}"
: "${VERCEL_CLI:?Set the path to a locally installed, reviewed Vercel executable}"
if [[ "${REBUILD_DATA:-0}" == "1" ]]; then
  "${PYTHON:-python}" dashboard/pipeline/run_dong_personas.py
  "${PYTHON:-python}" dashboard/pipeline/export_dashboard_static.py
fi
npm --prefix dashboard ci --ignore-scripts --no-fund
npm --prefix dashboard run build
"$VERCEL_CLI" deploy dashboard/dist --prod --yes
