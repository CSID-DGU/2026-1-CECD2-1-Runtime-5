#!/usr/bin/env bash
set -euo pipefail

TARGET_URL="${TARGET_URL:-http://localhost:3000}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-2}"
ITERATIONS="${ITERATIONS:--1}"
LOG_DIR="${LOG_DIR:-./attack_logs}"
ATTACK_SOURCE="${ATTACK_SOURCE:-http-loop}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/http_attack_runs.jsonl"

paths=(
  "/"
  "/rest/products/search?q=%27%20OR%201=1--"
  "/rest/user/login"
  "/api/Challenges/"
  "/assets/public/favicon_js.ico"
)

count=0
while true; do
  if [[ "$ITERATIONS" != "-1" && "$count" -ge "$ITERATIONS" ]]; then
    break
  fi

  for path in "${paths[@]}"; do
    attack_id="$(date -u +%Y%m%dT%H%M%SZ)-$count"
    ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    url="${TARGET_URL}${path}"
    status_code="$(curl -s -o /dev/null -w "%{http_code}" \
      -H "X-Attack-Source: ${ATTACK_SOURCE}" \
      -H "X-Attack-Id: ${attack_id}" \
      -H "User-Agent: codex-http-loop/1.0" \
      "$url" || true)"

    printf '{"timestamp":"%s","attack_source":"%s","attack_id":"%s","url":"%s","status_code":"%s"}\n' \
      "$ts" "$ATTACK_SOURCE" "$attack_id" "$url" "$status_code" >> "$LOG_FILE"
    sleep "$INTERVAL_SECONDS"
  done

  count=$((count + 1))
done
