# 실험 파이프라인 진입점 — Falco 이벤트를 받아 3개 실험 모드로 분기

import os
import datetime
import json
import time
import logging
from fastapi import FastAPI, Request

from remediation import DockerRemediator
from prompts import build_prompt
from cache import SemanticCache
from llm import get_llm_client
from storage import EventStorage

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ── 환경변수 ──────────────────────────────────────────────────────────────────
DATA_DIR        = os.getenv("DATA_DIR", "/app/data")
EXPERIMENT_MODE = os.getenv("EXPERIMENT_MODE", "baseline_a")
IS_ATTACK       = os.getenv("IS_ATTACK", "unknown")
CACHE_TTL       = int(os.getenv("CACHE_TTL", "60"))

# ── 전역 객체 ─────────────────────────────────────────────────────────────────
app         = FastAPI()
remediator  = DockerRemediator()
event_cache = SemanticCache(ttl_seconds=CACHE_TTL)
llm_client  = get_llm_client()
storage     = EventStorage(data_dir=DATA_DIR)

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
    rule_matched = remediation_result.get("status") != "ignored"

    if rule_matched:
        event_type    = "rule-matched"
        llm_called    = 0
        cache_hit     = 0
        gate_decision = "rule"
    else:
        # Step 2: 실험 모드별 분기
        if EXPERIMENT_MODE == "baseline_a":
            llm_result, p_tokens, c_tokens = await llm_client.call(build_prompt(payload))
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
            # 캐시 경쟁 조건 방지를 위해 락 사용
            async with event_cache.get_lock(payload):
                cached = event_cache.get(payload)
                if cached:
                    llm_result    = cached["result"]
                    cache_key_val = cached["cache_key"]
                    event_type    = "cache-hit"
                    llm_called    = 0
                    cache_hit     = 1
                    gate_decision = "cache-hit"
                else:
                    llm_result, p_tokens, c_tokens = await llm_client.call(build_prompt(payload))
                    cache_key_val = event_cache.set(payload, llm_result)
                    event_type    = "llm-analyzed"
                    llm_called    = 1
                    cache_hit     = 0
                    gate_decision = "llm"
        else:
            # 폴백: baseline_a
            llm_result, p_tokens, c_tokens = await llm_client.call(build_prompt(payload))
            event_type    = "llm-analyzed"
            llm_called    = 1
            cache_hit     = 0
            gate_decision = "llm"

    latency = int((time.time() - start_time) * 1000)

    # 이벤트 데이터 준비
    event_data = {
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
    }

    # CSV 행 준비
    csv_row = [
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
    ]

    # 저장소에 기록
    storage.log_event(event_data, csv_row)

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
