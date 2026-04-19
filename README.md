# Security Research Stack

## Components

- `falco` detects runtime events.
- `falcosidekick` forwards Falco events to `python-bridge`.
- `python-bridge` stores CSV and JSONL logs in `./bridge_data` and performs remediation.
- `falco-e2e-test` is a deterministic target container for repeatable Falco testing.

## Persistent logs

- CSV summary: `./bridge_data/security_stats.csv`
- Raw Falco events: `./bridge_data/falco_events.jsonl`
- Generated chart: `./bridge_data/research_graph.png`
- Attack loop logs: `./attack_logs/*.jsonl`

## Repeatable attack tests

### 1. HTTP attack loop

Use this to continuously hit Juice Shop with harmless but noisy probes:

```bash
bash attacks/http_attack_loop.sh
```

Optional env vars:

```bash
TARGET_URL=http://localhost:3000 INTERVAL_SECONDS=1 ITERATIONS=20 bash attacks/http_attack_loop.sh
```

### 2. Falco end-to-end loop

Use this to continuously trigger a deterministic Falco shell rule and verify full remediation:

```bash
bash attacks/falco_e2e_loop.sh
```

Optional env vars:

```bash
INTERVAL_SECONDS=3 ITERATIONS=10 bash attacks/falco_e2e_loop.sh
```

### 3. ZAP baseline scan

Use this for realistic web-app crawling and passive analysis against the running Juice Shop container:

```bash
bash attacks/zap_baseline.sh
```

Repeat scans:

```bash
ITERATIONS=-1 INTERVAL_SECONDS=60 bash attacks/zap_baseline.sh
```

Reports are written to `./zap_reports`.

### 4. ZAP full scan

Use this when you want a more aggressive active scan:

```bash
bash attacks/zap_full_scan.sh
```

This is more realistic than Nikto for application testing, but it is also noisier and can interfere with auto-remediation.

### 5. LLM path test loop

Use this to force non-critical webhook events so Ollama token usage is guaranteed to accumulate:

```bash
bash attacks/llm_test_loop.sh
```

Example:

```bash
ITERATIONS=5 INTERVAL_SECONDS=2 bash attacks/llm_test_loop.sh
```

### 6. LLM stats summary

Summarize only the LLM-analyzed rows from the persisted CSV:

```bash
bash scripts/llm_stats.sh
```

### 7. Mixed day-long simulator

Use this to keep collecting mixed logs all day. It randomly mixes:

- normal browsing traffic
- suspicious HTTP probes
- non-critical LLM webhook events
- real Falco remediation triggers
- periodic ZAP baseline scans

```bash
bash attacks/mixed_traffic_simulator.sh
```

Example:

```bash
MIN_SLEEP_SECONDS=10 MAX_SLEEP_SECONDS=45 ZAP_EVERY_N_CYCLES=30 bash attacks/mixed_traffic_simulator.sh
```

Logs are written to `./attack_logs/mixed_traffic_runs.jsonl`.

Recommended modes:

- For uninterrupted collection, temporarily use `REMEDIATION_DRY_RUN=true`
- For full detection/remediation validation, leave remediation enabled but keep the destructive path limited to `falco-e2e-test`

### Run as a persistent service

If you want collection to continue after your SSH session ends, run the simulator as a Compose service:

```bash
docker compose up -d traffic-simulator
```

Check status and logs:

```bash
docker compose ps traffic-simulator
docker logs -f traffic-simulator
```

The Docker daemon keeps these containers running independently of your shell session.

## Primary DAST: ZAP

ZAP is the primary DAST engine for this repo because it is open source, fully self-hosted, and works without any external platform account.

Main commands:

```bash
bash attacks/zap_baseline.sh
bash attacks/zap_full_scan.sh
bash scripts/zap_recent.sh
```

Recommended usage:

- `zap_baseline.sh` for recurring safe scans
- `zap_full_scan.sh` for stronger active probing
- `traffic-simulator` for long-running mixed traffic and periodic baseline scans

## StackHawk note

StackHawk-related files are left in the repo only as optional future reference. They are not required for the current self-hosted DAST workflow.

## Nuclei notes

Nuclei is fine for HTTP scanning, but it will not automatically produce rich syscall evidence for every request. Use it as an app-layer probe source, then correlate it with:

- Juice Shop or reverse proxy access logs
- `./attack_logs/http_attack_runs.jsonl`
- `./bridge_data/falco_events.jsonl`
- `./bridge_data/security_stats.csv`

Recommended practice:

- Start with `REMEDIATION_DRY_RUN=true` for any high-volume scan
- Use a dedicated scan target container instead of your primary demo app
- Limit concurrency to avoid swamping Ollama-backed analysis

## Tool choice

- `ZAP baseline` is the safest default for repeated web scanning.
- `ZAP full scan` is the more realistic active attack option.
- `Nikto` is still useful for old-school web server checks, but it is weaker for modern app flow testing than ZAP.
