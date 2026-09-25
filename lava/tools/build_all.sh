#!/usr/bin/env bash
# Regenerate every deliverable from data/existing.json + data/layout.json.
set -euo pipefail
cd "$(dirname "$0")/.."
python3 tools/make_layout.py
python3 tools/validate.py data/layout.json --json data/validation.json
python3 tools/plan_svg.py data/layout.json --validation data/validation.json
NODE_PATH="$(npm root -g)" node tools/export_sheets.js plan
python3 tools/export_dxf.py
python3 tools/report.py data/layout.json data/validation.json
python3 tools/permit_docs.py
if [ -f tools/build_app.py ]; then python3 tools/build_app.py; fi
echo "OK: plan/ (PDF, PNG, DXF), docs/INFORME_TEST_FIT.md, docs/permisos/, data/report.json, app/"
