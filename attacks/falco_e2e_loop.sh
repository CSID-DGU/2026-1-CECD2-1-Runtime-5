#!/usr/bin/env bash
set -euo pipefail

TARGET_CONTAINER="${TARGET_CONTAINER:-falco-e2e-test}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-5}"
ITERATIONS="${ITERATIONS:--1}"
LOG_DIR="${LOG_DIR:-./attack_logs}"

mkdir -p "$LOG_DIR"
LOG_FILE="$LOG_DIR/falco_e2e_runs.jsonl"

count=0
while true; do
  if [[ "$ITERATIONS" != "-1" && "$count" -ge "$ITERATIONS" ]]; then
    break
  fi

  if ! docker ps --format '{{.Names}}' | grep -qx "$TARGET_CONTAINER"; then
    docker start "$TARGET_CONTAINER" >/dev/null
  fi

  attack_id="$(date -u +%Y%m%dT%H%M%SZ)-$count"
  cmd="echo codex-e2e-trigger ${attack_id}"
  docker exec "$TARGET_CONTAINER" sh -c "$cmd" >/dev/null

  printf '{"timestamp":"%s","attack_source":"falco-e2e-loop","attack_id":"%s","target_container":"%s","command":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$attack_id" "$TARGET_CONTAINER" "$cmd" >> "$LOG_FILE"

  count=$((count + 1))
  sleep "$INTERVAL_SECONDS"
done
