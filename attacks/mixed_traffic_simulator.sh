#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET_URL="${TARGET_URL:-http://127.0.0.1:3000}"
WEBHOOK_URL="${WEBHOOK_URL:-http://127.0.0.1:5000/webhook}"
FALCO_TARGET_CONTAINER="${FALCO_TARGET_CONTAINER:-falco-e2e-test}"
LOG_DIR="${LOG_DIR:-./attack_logs}"
MIN_SLEEP_SECONDS="${MIN_SLEEP_SECONDS:-5}"
MAX_SLEEP_SECONDS="${MAX_SLEEP_SECONDS:-30}"
ITERATIONS="${ITERATIONS:--1}"
ENABLE_ZAP="${ENABLE_ZAP:-true}"
ZAP_EVERY_N_CYCLES="${ZAP_EVERY_N_CYCLES:-25}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/mixed_traffic_runs.jsonl"

normal_paths=(
  "/"
  "/#/search?q=apple"
  "/rest/products/search?q=juice"
  "/rest/products/search?q=banana"
  "/api/Challenges/"
  "/assets/public/images/uploads/"
  "/rest/languages"
  "/rest/products/1/reviews"
)

probe_paths=(
  "/rest/products/search?q=%27%20OR%201=1--"
  "/rest/user/login"
  "/ftp"
  "/ftp/coupons_2013.md.bak"
  "/support/logs"
)

llm_rules=(
  "Write below binary dir"
  "Modify Shell Configuration File"
)

llm_priorities=(
  "Warning"
  "Error"
)

count=0
while true; do
  if [[ "$ITERATIONS" != "-1" && "$count" -ge "$ITERATIONS" ]]; then
    break
  fi

  cycle_id="$(date -u +%Y%m%dT%H%M%SZ)-$count"
  action_roll=$((RANDOM % 100))
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  action=""
  result=""

  if [[ "$ENABLE_ZAP" == "true" && "$count" -gt 0 && $((count % ZAP_EVERY_N_CYCLES)) -eq 0 ]]; then
    action="zap-baseline"
    report_prefix="mixed-zap-${cycle_id}"
    if ITERATIONS=1 REPORT_PREFIX="$report_prefix" SPIDER_MINS=1 MAX_TIME_MINS=3 \
      bash "${REPO_DIR}/attacks/zap_baseline.sh" >/dev/null 2>&1; then
      result="completed"
    else
      result="failed"
    fi
  elif [[ "$action_roll" -lt 45 ]]; then
    action="normal-http"
    path="${normal_paths[$((RANDOM % ${#normal_paths[@]}))]}"
    status_code="$(curl -s -o /dev/null -w "%{http_code}" \
      -H "X-Traffic-Source: normal-user" \
      -H "X-Cycle-Id: ${cycle_id}" \
      -H "User-Agent: codex-normal-browse/1.0" \
      "${TARGET_URL}${path}" || true)"
    result="status=${status_code} path=${path}"
  elif [[ "$action_roll" -lt 70 ]]; then
    action="suspicious-http"
    path="${probe_paths[$((RANDOM % ${#probe_paths[@]}))]}"
    status_code="$(curl -s -o /dev/null -w "%{http_code}" \
      -H "X-Traffic-Source: suspicious-probe" \
      -H "X-Cycle-Id: ${cycle_id}" \
      -H "User-Agent: codex-suspicious-probe/1.0" \
      "${TARGET_URL}${path}" || true)"
    result="status=${status_code} path=${path}"
  elif [[ "$action_roll" -lt 90 ]]; then
    action="llm-warning"
    rule="${llm_rules[$((RANDOM % ${#llm_rules[@]}))]}"
    priority="${llm_priorities[$((RANDOM % ${#llm_priorities[@]}))]}"
    payload="$(cat <<JSON
{"rule":"${rule}","priority":"${priority}","output":"Mixed simulator event ${cycle_id}: ${rule}","output_fields":{"container.id":"mixed-llm-target","container.name":"mixed-llm-target","proc.cmdline":"mixed-llm ${cycle_id}"},"tags":["llm","simulator","mixed"]}
JSON
)"
    response="$(curl -s -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' -d "$payload" || true)"
    result="$(printf '%s' "$response" | tr '\n' ' ' | cut -c1-300)"
  else
    action="falco-remediation"
    if ! docker ps --format '{{.Names}}' | grep -qx "$FALCO_TARGET_CONTAINER"; then
      docker start "$FALCO_TARGET_CONTAINER" >/dev/null 2>&1 || true
    fi
    if docker exec "$FALCO_TARGET_CONTAINER" sh -c "echo codex-e2e-trigger ${cycle_id}" >/dev/null 2>&1; then
      result="triggered"
    else
      result="trigger-failed"
    fi
  fi

  printf '{"timestamp":"%s","cycle_id":"%s","action":"%s","result":"%s"}\n' \
    "$ts" "$cycle_id" "$action" "$(printf '%s' "$result" | tr '"' "'" )" >> "$LOG_FILE"

  sleep_for=$((MIN_SLEEP_SECONDS + RANDOM % (MAX_SLEEP_SECONDS - MIN_SLEEP_SECONDS + 1)))
  sleep "$sleep_for"
  count=$((count + 1))
done
