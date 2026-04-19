#!/usr/bin/env bash
set -euo pipefail

WEBHOOK_URL="${WEBHOOK_URL:-http://127.0.0.1:5000/webhook}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-3}"
ITERATIONS="${ITERATIONS:--1}"
LOG_DIR="${LOG_DIR:-./attack_logs}"
CONTAINER_NAME="${CONTAINER_NAME:-llm-test-target}"
CONTAINER_ID="${CONTAINER_ID:-llm-test-container}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/llm_test_runs.jsonl"

count=0
while true; do
  if [[ "$ITERATIONS" != "-1" && "$count" -ge "$ITERATIONS" ]]; then
    break
  fi

  attack_id="$(date -u +%Y%m%dT%H%M%SZ)-$count"
  ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  payload="$(cat <<JSON
{"rule":"Write below binary dir","priority":"Warning","output":"LLM test event ${attack_id}: file below a known binary directory opened for writing","output_fields":{"container.id":"${CONTAINER_ID}","container.name":"${CONTAINER_NAME}","proc.cmdline":"llm-test ${attack_id}"},"tags":["llm","codex","test"]}
JSON
)"

  response="$(curl -s -X POST "$WEBHOOK_URL" -H 'Content-Type: application/json' -d "$payload")"
  printf '{"timestamp":"%s","attack_source":"llm-test-loop","attack_id":"%s","response":%s}\n' \
    "$ts" "$attack_id" "$response" >> "$LOG_FILE"

  count=$((count + 1))
  sleep "$INTERVAL_SECONDS"
done
