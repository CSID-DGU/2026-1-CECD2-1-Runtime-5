#!/usr/bin/env bash
set -euo pipefail

CSV_FILE="${CSV_FILE:-./bridge_data/security_stats.csv}"

if [[ ! -f "$CSV_FILE" ]]; then
  echo "CSV not found: $CSV_FILE" >&2
  exit 1
fi

awk -F, '
BEGIN {
  llm_calls = 0
  prompt_total = 0
  completion_total = 0
  latency_total = 0
}
NR == 1 { next }
$2 == "LLM-analyzed" {
  llm_calls++
  prompt_total += $5
  completion_total += $6
  latency_total += $7
}
END {
  print "llm_calls=" llm_calls
  print "prompt_tokens_total=" prompt_total
  print "completion_tokens_total=" completion_total
  print "total_tokens=" prompt_total + completion_total
  if (llm_calls > 0) {
    print "avg_latency_ms=" int(latency_total / llm_calls)
  } else {
    print "avg_latency_ms=0"
  }
}' "$CSV_FILE"

echo
echo "recent_llm_rows:"
awk -F, 'NR==1 || $2=="LLM-analyzed"' "$CSV_FILE" | tail -n 6
