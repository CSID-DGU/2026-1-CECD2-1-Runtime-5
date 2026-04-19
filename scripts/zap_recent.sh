#!/usr/bin/env bash
set -euo pipefail

REPORT_DIR="${REPORT_DIR:-./zap_reports}"

if [[ ! -d "$REPORT_DIR" ]]; then
  echo "Report directory not found: $REPORT_DIR" >&2
  exit 1
fi

latest_json="$(find "$REPORT_DIR" -maxdepth 1 -type f -name 'zap-*.json' | sort | tail -n 1)"
latest_html="$(find "$REPORT_DIR" -maxdepth 1 -type f -name 'zap-*.html' | sort | tail -n 1)"
latest_md="$(find "$REPORT_DIR" -maxdepth 1 -type f -name 'zap-*.md' | sort | tail -n 1)"

if [[ -z "$latest_json" ]]; then
  echo "No ZAP JSON report found in $REPORT_DIR" >&2
  exit 1
fi

echo "latest_json=$latest_json"
if [[ -n "$latest_html" ]]; then
  echo "latest_html=$latest_html"
fi
if [[ -n "$latest_md" ]]; then
  echo "latest_md=$latest_md"
fi

echo
python3 - "$latest_json" <<'PY'
import json
import sys

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

site = data.get("site", [])
alerts = []
for s in site:
    alerts.extend(s.get("alerts", []))

print(f"alerts_total={len(alerts)}")
for alert in alerts[:10]:
    name = alert.get("name", "unknown")
    risk = alert.get("riskdesc", "unknown")
    count = len(alert.get("instances", []))
    print(f"- {name} | risk={risk} | instances={count}")
PY
