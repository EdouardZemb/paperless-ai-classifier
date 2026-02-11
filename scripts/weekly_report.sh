#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
OUT_DIR="$ROOT_DIR/_bmad-output/implementation-artifacts"
DATE=$(date '+%Y-%m-%d %H:%M')
WEEK=$(date '+%G-W%V')
REPORT_PATH="$OUT_DIR/maintenance-weekly-$WEEK.md"

mkdir -p "$OUT_DIR"

python3 - <<PY > "$REPORT_PATH"
import json
from pathlib import Path
from datetime import datetime, timedelta

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

# Daily trend (last 7 days)
by_day = {}
cutoff = datetime.now() - timedelta(days=6)
for r in cls:
    ts = r.get('timestamp')
    if not ts:
        continue
    try:
        dt = datetime.fromisoformat(ts)
    except Exception:
        continue
    if dt < cutoff:
        continue
    day = dt.strftime('%Y-%m-%d')
    by_day.setdefault(day, 0)
    by_day[day] += 1

print(f"# Maintenance Weekly Report — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print()
print("## Summary")
print(f"- Total classifications: {len(cls)}")
print(f"- Auto: {auto_count}")
print(f"- Manual: {manual_count}")
print(f"- Review pending: {review_pending}")
print(f"- Suggestions pending: {pending} (validated: {validated}, rejected: {rejected})")
print()
print("## Last 7 days volume")
if by_day:
    for day in sorted(by_day.keys()):
        print(f"- {day}: {by_day[day]} document(s)")
else:
    print("- No recent data")
PY


echo "$REPORT_PATH"
