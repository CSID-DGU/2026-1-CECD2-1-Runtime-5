#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

TARGET_CONTAINER="${TARGET_CONTAINER:-juice-shop}"
TARGET_PORT="${TARGET_PORT:-3000}"
ZAP_IMAGE="${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:stable}"
REPORT_DIR="${REPORT_DIR:-./zap_reports}"
REPORT_PREFIX="${REPORT_PREFIX:-zap-full}"
MAX_TIME_MINS="${MAX_TIME_MINS:-10}"
DEBUG_FLAG="${DEBUG_FLAG:-false}"

mkdir -p "$REPORT_DIR"

network_name="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$TARGET_CONTAINER" | head -n1 | tr -d '[:space:]')"
if [[ -z "$network_name" ]]; then
  echo "Failed to resolve Docker network for target container: $TARGET_CONTAINER" >&2
  exit 1
fi

ts="$(date -u +%Y%m%dT%H%M%SZ)"
html_report="${REPORT_PREFIX}-${ts}.html"
json_report="${REPORT_PREFIX}-${ts}.json"
md_report="${REPORT_PREFIX}-${ts}.md"
target_url="http://${TARGET_CONTAINER}:${TARGET_PORT}"

debug_args=()
if [[ "$DEBUG_FLAG" == "true" ]]; then
  debug_args+=("-d")
fi

docker run --rm \
  --network "$network_name" \
  -v "${REPO_DIR}/${REPORT_DIR#./}:/zap/wrk/:rw" \
  -t "$ZAP_IMAGE" \
  zap-full-scan.py \
  -t "$target_url" \
  -T "$MAX_TIME_MINS" \
  -r "$html_report" \
  -J "$json_report" \
  -w "$md_report" \
  -I \
  "${debug_args[@]}"
