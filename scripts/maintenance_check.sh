#!/usr/bin/env bash
set -euo pipefail

BASE_URL=${BASE_URL:-http://127.0.0.1:5001}
ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT_DIR="$ROOT_DIR/_bmad-output/implementation-artifacts"
DATE=$(date '+%Y-%m-%d %H:%M')
REPORT_PATH="$OUT_DIR/maintenance-report-$(date +%F).md"

mkdir -p "$OUT_DIR"

health_json=$(curl -s "$BASE_URL/health" || true)

# Compute counts
python_report=$(python3 - <<'PY'
import json
from pathlib import Path

root = Path("/home/edouard/paperless/ai-classifier")
cls_path = root / "models" / "classifications.jsonl"
actions_path = root / "models" / "actions.jsonl"
suggestions_path = root / "config" / "suggested_types.json"

cls = []
actions = []

if cls_path.exists():
    for line in cls_path.read_text().splitlines():
        if line.strip():
            try: cls.append(json.loads(line))
            except: pass

if actions_path.exists():
    for line in actions_path.read_text().splitlines():
        if line.strip():
            try: actions.append(json.loads(line))
            except: pass

resolved = {a['document_id'] for a in actions if a.get('action') != 'reporter'}
review_total = sum(1 for r in cls if r.get('classification', {}).get('final_recommendation', {}).get('action') == 'review_needed')
review_pending = sum(1 for r in cls if r.get('classification', {}).get('final_recommendation', {}).get('action') == 'review_needed' and r.get('document_id') not in resolved)

auto_count = sum(1 for r in cls if r.get('classification', {}).get('final_recommendation', {}).get('action') == 'auto_classify')
manual_count = sum(1 for r in cls if r.get('classification', {}).get('final_recommendation', {}).get('action') == 'manual_classification')

suggestions = {}
if suggestions_path.exists():
    try:
        suggestions = json.loads(suggestions_path.read_text())
    except Exception:
        suggestions = {}

pending = sum(1 for _, s in suggestions.items() if not s.get('validated') and not s.get('rejected'))
validated = sum(1 for _, s in suggestions.items() if s.get('validated'))
rejected = sum(1 for _, s in suggestions.items() if s.get('rejected'))

print(json.dumps({
    "classifications": len(cls),
    "actions": len(actions),
    "review_total": review_total,
    "review_pending": review_pending,
    "auto": auto_count,
    "manual": manual_count,
    "suggestions_pending": pending,
    "suggestions_validated": validated,
    "suggestions_rejected": rejected
}))
PY
)

cat > "$REPORT_PATH" <<EOF
# Maintenance Report — $DATE

## Health

goal: vérifier que les services sont disponibles

~~~json
${health_json}
~~~

## Counts

$(python3 - <<PY
import json
print(json.dumps(json.loads('''$python_report'''), indent=2))
PY
)

## Notes
- Base URL: $BASE_URL
- Report: $REPORT_PATH
EOF

echo "$REPORT_PATH"
