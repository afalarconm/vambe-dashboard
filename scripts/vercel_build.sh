#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
cd apps/web && npm run build
cd ../..
PY=$(command -v python3 || command -v python)
"$PY" scripts/ingest.py
"$PY" scripts/load_labels.py
