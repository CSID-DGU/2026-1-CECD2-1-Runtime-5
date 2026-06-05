# 실험 파이프라인 진입점 — Falco 이벤트를 받아 3개 실험 모드로 분기

import csv
import os
import datetime
import json
import time
from fastapi import FastAPI, Request
import httpx

from remediation import DockerRemediator
from prompts import build_prompt
from cache import SemanticCache

# ── 환경변수 ──────────────────────────────────────────────────────────────────
DATA_DIR        = os.getenv("DATA_DIR", "/app/data")
OLLAMA_URL      = "http://ollama:11434/api/generate"
EXPERIMENT_MODE = os.getenv("EXPERIMENT_MODE", "baseline_a")
IS_ATTACK       = os.getenv("IS_ATTACK", "unknown")
CACHE_TTL       = int(os.getenv("CACHE_TTL", "60"))

CSV_FILE        = os.path.join(DATA_DIR, "security_stats.csv")
RAW_EVENTS_FILE = os.path.join(DATA_DIR, "falco_events.jsonl")

# ── 전역 객체 ─────────────────────────────────────────────────────────────────
app         = FastAPI()
remediator  = DockerRemediator()
event_cache = SemanticCache(ttl_seconds=CACHE_TTL)

os.makedirs(DATA_DIR, exist_ok=True)

# ── CSV 헤더 ──────────────────────────────────────────────────────────────────
CSV_HEADERS = [
    # 기존 17개 필드 (제거 금지)
    "timestamp", "event_type", "rule_name", "priority",
    "prompt_tokens", "completion_tokens", "latency_ms",
    "remediation_status", "remediation_action", "mitre_technique",
    "target_container", "attack_source", "attack_label",
    "attack_id", "container_id", "container_image", "event_source",
    # 추가 필드
    "experiment_mode", "ground_truth", "rule_matched",
    "llm_called", "cache_hit", "cache_key",
    "gate_decision", "llm_action", "llm_threat_level",
    "cache_ttl",
]

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        csv.writer(f).writerow(CSV_HEADERS)


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

async def call_llm(prompt: str) -> tuple[dict, int, int]:
    """Ollama 호출 후 JSON 파싱. 파싱 실패 시 ignore 폴백."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(OLLAMA_URL, json={
            "model": "qwen2.5:0.5b",
            "prompt": prompt,
            "stream": False,
        }, timeout=30.0)
        res_json  = resp.json()
        p_tokens  = res_json.get("prompt_eval_count", 0)
        c_tokens  = res_json.get("eval_count", 0)
        raw_text  = res_json.get("response", "")
        try:
            start  = raw_text.index("{")
            end    = raw_text.rindex("}") + 1
            result = json.loads(raw_text[start:end])
        except (ValueError, json.JSONDecodeError):
            result = {"action": "ignore", "threat_level": "none", "reason": "parse error"}
        return result, p_tokens, c_tokens


# ── 웹훅 핸들러 ───────────────────────────────────────────────────────────────

@app.post("/webhook")
async def handle_falco_alert(request: Request):
    start_time = time.time()
    payload    = await request.json()

    rule_name   = payload.get("rule", "Unknown")
    priority    = payload.get("priority", "Debug")
    correlation = extract_correlation_fields(payload)

    p_tokens, c_tokens = 0, 0
    llm_result:   dict = {}
    cache_key_val: str = ""

    # Step 1: remediation 룰 매칭
    remediation_result = remediator.remediate(payload)
    # status == "ignored" → _classify()가 매핑을 찾지 못한 경우
    rule_matched = remediation_result.get("status") != "ignored"

    if rule_matched:
        event_type    = "rule-matched"
        llm_called    = 0
        cache_hit     = 0
        gate_decision = "rule"

    else:
        # Step 2: 실험 모드별 분기 (3개)
        if EXPERIMENT_MODE == "baseline_a":
            llm_result, p_tokens, c_tokens = await call_llm(build_prompt(payload))
            event_type    = "llm-analyzed"
            llm_called    = 1
            cache_hit     = 0
            gate_decision = "llm"

        elif EXPERIMENT_MODE == "baseline_b":
            event_type    = "ignored"
            llm_called    = 0
            cache_hit     = 0
            gate_decision = "ignored"

        elif EXPERIMENT_MODE == "proposed":
            cached = event_cache.get(payload)
            if cached:
                llm_result    = cached["result"]
                cache_key_val = cached["cache_key"]
                event_type    = "cache-hit"
                llm_called    = 0
                cache_hit     = 1
                gate_decision = "cache-hit"
            else:
                llm_result, p_tokens, c_tokens = await call_llm(build_prompt(payload))
                cache_key_val = event_cache.set(payload, llm_result)
                event_type    = "llm-analyzed"
                llm_called    = 1
                cache_hit     = 0
                gate_decision = "llm"

        else:
            # 알 수 없는 모드: baseline_a로 폴백
            llm_result, p_tokens, c_tokens = await call_llm(build_prompt(payload))
            event_type    = "llm-analyzed"
            llm_called    = 1
            cache_hit     = 0
            gate_decision = "llm"

    latency = int((time.time() - start_time) * 1000)

    # JSONL 원본 이벤트 기록
    with open(RAW_EVENTS_FILE, mode="a", encoding="utf-8") as raw_file:
        raw_file.write(json.dumps({
            "timestamp":       datetime.datetime.now().isoformat(),
            "payload":         payload,
            "correlation":     correlation,
            "remediation":     remediation_result,
            "event_type":      event_type,
            "latency_ms":      latency,
            "experiment_mode": EXPERIMENT_MODE,
            "ground_truth":    IS_ATTACK,
            "rule_matched":    int(rule_matched),
            "llm_called":      llm_called,
            "cache_hit":       cache_hit,
            "gate_decision":   gate_decision,
            "llm_result":      llm_result,
        }, ensure_ascii=True) + "\n")

    # CSV 실시간 기록
    with open(CSV_FILE, mode='a', newline='') as f:
        csv.writer(f).writerow([
            datetime.datetime.now().isoformat(),
            event_type,
            rule_name,
            priority,
            p_tokens,
            c_tokens,
            latency,
            remediation_result.get("status", "unknown"),
            remediation_result.get("action", ""),
            remediation_result.get("mitre", {}).get("technique_id", ""),
            remediation_result.get("target", ""),
            correlation["attack_source"],
            correlation["attack_label"],
            correlation["attack_id"],
            correlation["container_id"],
            correlation["container_image"],
            correlation["event_source"],
            # 추가 필드
            EXPERIMENT_MODE,
            IS_ATTACK,
            int(rule_matched),
            llm_called,
            cache_hit,
            cache_key_val,
            gate_decision,
            llm_result.get("action", ""),
            llm_result.get("threat_level", ""),
            CACHE_TTL,
        ])

    return {
        "status":          "success",
        "event":           event_type,
        "remediation":     remediation_result,
        "gate_decision":   gate_decision,
        "experiment_mode": EXPERIMENT_MODE,
    }


# ── 상태 엔드포인트 ───────────────────────────────────────────────────────────

@app.get("/status")
def status():
    return {
        "experiment_mode": EXPERIMENT_MODE,
        "is_attack":       IS_ATTACK,
        "cache_ttl":       CACHE_TTL,
        "cache_hit_rate":  f"{event_cache.hit_rate:.1%}",
        "cache_hits":      event_cache.hits,
        "cache_misses":    event_cache.misses,
    }


# ── 헬퍼 ─────────────────────────────────────────────────────────────────────

def extract_correlation_fields(payload: dict) -> dict[str, str]:
    output_fields = payload.get("output_fields", {}) or {}
    tags          = payload.get("tags", []) or []
    tag_string    = ",".join(str(tag) for tag in tags)

    attack_source = "manual"
    if "nuclei" in tag_string.lower():
        attack_source = "nuclei"
    elif "codex" in tag_string.lower():
        attack_source = "codex-loop"

    container_id    = str(output_fields.get("container.id", "") or payload.get("container.id", ""))
    container_image = "/".join(
        part for part in [
            str(output_fields.get("container.image.repository", "")).strip(),
            str(output_fields.get("container.image.tag", "")).strip(),
        ] if part
    )

    return {
        "attack_source":  attack_source,
        "attack_label":   str(payload.get("rule", "unknown")),
        "attack_id":      str(output_fields.get("proc.cmdline", "") or payload.get("uuid", "")),
        "container_id":   container_id,
        "container_image": container_image,
        "event_source":   str(payload.get("source", "unknown")),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
