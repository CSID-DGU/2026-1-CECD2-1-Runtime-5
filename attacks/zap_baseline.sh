#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET_CONTAINER="${TARGET_CONTAINER:-juice-shop}"
TARGET_PORT="${TARGET_PORT:-3000}"
ZAP_IMAGE="${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:stable}"
SPIDER_MINS="${SPIDER_MINS:-1}"
MAX_TIME_MINS="${MAX_TIME_MINS:-3}"
REPORT_DIR="${REPORT_DIR:-./zap_reports}"
REPORT_PREFIX="${REPORT_PREFIX:-zap-baseline}"
DEBUG_FLAG="${DEBUG_FLAG:-false}"
ITERATIONS="${ITERATIONS:-1}"
INTERVAL_SECONDS="${INTERVAL_SECONDS:-30}"

mkdir -p "$REPORT_DIR"

network_name="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$TARGET_CONTAINER" | head -n1 | tr -d '[:space:]')"
if [[ -z "$network_name" ]]; then
  echo "Failed to resolve Docker network for target container: $TARGET_CONTAINER" >&2
  exit 1
fi

debug_args=()
if [[ "$DEBUG_FLAG" == "true" ]]; then
  debug_args+=("-d")
fi

count=0
while true; do
  if [[ "$ITERATIONS" != "-1" && "$count" -ge "$ITERATIONS" ]]; then
    break
  fi

  ts="$(date -u +%Y%m%dT%H%M%SZ)"
  html_report="${REPORT_PREFIX}-${ts}.html"
  json_report="${REPORT_PREFIX}-${ts}.json"
  md_report="${REPORT_PREFIX}-${ts}.md"
  target_url="http://${TARGET_CONTAINER}:${TARGET_PORT}"

  docker run --rm \
    --network "$network_name" \
    -v "${REPO_DIR}/${REPORT_DIR#./}:/zap/wrk/:rw" \
    -t "$ZAP_IMAGE" \
    zap-baseline.py \
    -t "$target_url" \
    -m "$SPIDER_MINS" \
    -T "$MAX_TIME_MINS" \
    -r "$html_report" \
    -J "$json_report" \
    -w "$md_report" \
    -I \
    "${debug_args[@]}"

  count=$((count + 1))
  if [[ "$ITERATIONS" != "-1" && "$count" -ge "$ITERATIONS" ]]; then
    break
  fi
  sleep "$INTERVAL_SECONDS"
done
