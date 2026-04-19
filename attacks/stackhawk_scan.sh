#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

STACKHAWK_CONFIG="${STACKHAWK_CONFIG:-stackhawk/stackhawk.yml}"
STACKHAWK_IMAGE="${STACKHAWK_IMAGE:-stackhawk/hawkscan:latest}"

if [[ ! -f "${REPO_DIR}/${STACKHAWK_CONFIG}" ]]; then
  echo "Missing config file: ${REPO_DIR}/${STACKHAWK_CONFIG}" >&2
  echo "Copy stackhawk/stackhawk.yml.example to stackhawk/stackhawk.yml and fill SH_APPLICATION_ID / HAWK_API_KEY first." >&2
  exit 1
fi

if [[ -z "${HAWK_API_KEY:-}" ]]; then
  echo "HAWK_API_KEY is not set." >&2
  exit 1
fi

docker run --rm \
  --network security-research_default \
  -e API_KEY="${HAWK_API_KEY}" \
  -e SH_APP_HOST="${SH_APP_HOST:-http://juiceshop:3000}" \
  -e SH_APPLICATION_ID="${SH_APPLICATION_ID:-}" \
  -e SH_ENVIRONMENT="${SH_ENVIRONMENT:-Development}" \
  -v "${REPO_DIR}:/hawk:rw" \
  -t "${STACKHAWK_IMAGE}" \
  --config "/hawk/${STACKHAWK_CONFIG}"
