import csv
import os
import datetime
import json
import time
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse
import httpx
import pandas as pd
import matplotlib.pyplot as plt

from remediation import DockerRemediator

app = FastAPI()

# 파일 및 경로 설정
DATA_DIR = os.getenv("DATA_DIR", "/app/data")
CSV_FILE = os.path.join(DATA_DIR, "security_stats.csv")
GRAPH_FILE = os.path.join(DATA_DIR, "research_graph.png")
RAW_EVENTS_FILE = os.path.join(DATA_DIR, "falco_events.jsonl")
OLLAMA_URL = "http://ollama:11434/api/generate"
remediator = DockerRemediator()

os.makedirs(DATA_DIR, exist_ok=True)

# CSV 초기화 (파일이 없으면 헤더 작성)
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "event_type",
            "rule_name",
            "priority",
            "prompt_tokens",
            "completion_tokens",
            "latency_ms",
            "remediation_status",
            "remediation_action",
            "mitre_technique",
            "target_container",
            "attack_source",
            "attack_label",
            "attack_id",
            "container_id",
            "container_image",
            "event_source",
        ])

@app.post("/webhook")
async def handle_falco_alert(request: Request):
    start_time = time.time()
    payload = await request.json()
    
    rule_name = payload.get("rule", "Unknown")
    priority = payload.get("priority", "Debug")
    output = payload.get("output", "")
    correlation = extract_correlation_fields(payload)
    
    event_type = "Rule-based"
    p_tokens, c_tokens = 0, 0
    remediation_result = remediator.remediate(payload)
    
    # 1. 높은 심각도 이벤트는 수집기에서 먼저 분류한다.
    if priority == "Critical":
        event_type = "Rule-based (Remediation)"
    else:
        # 2. 그 외는 LLM 호출
        event_type = "LLM-analyzed"
        async with httpx.AsyncClient() as client:
            resp = await client.post(OLLAMA_URL, json={
                "model": "qwen2.5:0.5b",
                "prompt": f"Score this log (0-10): {output}",
                "stream": False
            }, timeout=30.0)
            res_json = resp.json()
            p_tokens = res_json.get("prompt_eval_count", 0)
            c_tokens = res_json.get("eval_count", 0)

    latency = int((time.time() - start_time) * 1000) # 밀리초 단위

    with open(RAW_EVENTS_FILE, mode="a", encoding="utf-8") as raw_file:
        raw_file.write(json.dumps({
            "timestamp": datetime.datetime.now().isoformat(),
            "payload": payload,
            "correlation": correlation,
            "remediation": remediation_result,
            "event_type": event_type,
            "latency_ms": latency,
        }, ensure_ascii=True) + "\n")

    # 3. CSV에 실시간 기록
    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
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
        ])

    return {
        "status": "success",
        "event": event_type,
        "remediation": remediation_result,
    }

# 그래프 생성 및 다운로드 엔드포인트
@app.get("/generate-graph")
def generate_graph():
    if not os.path.exists(CSV_FILE):
        return {"error": "No data available"}

    df = pd.read_csv(CSV_FILE)
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # 누적 토큰 사용량 계산
    df['total_tokens'] = df['prompt_tokens'] + df['completion_tokens']
    df['cumulative_tokens'] = df['total_tokens'].cumsum()

    # 시각화 설정
    plt.figure(figsize=(10, 6))
    plt.plot(df['timestamp'], df['cumulative_tokens'], marker='o', linestyle='-', color='b', label='Cumulative Tokens')
    plt.title('LLM Resource Usage Over Time')
    plt.xlabel('Time')
    plt.ylabel('Total Tokens Used')
    plt.xticks(rotation=45)
    plt.grid(True)
    plt.legend()
    plt.tight_layout()
    
    plt.savefig(GRAPH_FILE)
    plt.close()
    
    return FileResponse(GRAPH_FILE, media_type="image/png", filename=GRAPH_FILE)

# CSV 파일 다운로드 엔드포인트
@app.get("/download-csv")
def download_csv():
    return FileResponse(CSV_FILE, media_type="text/csv", filename=CSV_FILE)


@app.get("/download-events")
def download_events():
    if not os.path.exists(RAW_EVENTS_FILE):
        return {"error": "No event data available"}
    return FileResponse(RAW_EVENTS_FILE, media_type="application/jsonl", filename=os.path.basename(RAW_EVENTS_FILE))


def extract_correlation_fields(payload: dict) -> dict[str, str]:
    output_fields = payload.get("output_fields", {}) or {}
    tags = payload.get("tags", []) or []
    tag_string = ",".join(str(tag) for tag in tags)
    attack_source = "manual"
    if "nuclei" in tag_string.lower():
        attack_source = "nuclei"
    elif "codex" in tag_string.lower():
        attack_source = "codex-loop"

    container_id = str(output_fields.get("container.id", "") or payload.get("container.id", ""))
    container_image = "/".join(
        part for part in [
            str(output_fields.get("container.image.repository", "")).strip(),
            str(output_fields.get("container.image.tag", "")).strip(),
        ] if part
    )

    return {
        "attack_source": attack_source,
        "attack_label": str(payload.get("rule", "unknown")),
        "attack_id": str(output_fields.get("proc.cmdline", "") or payload.get("uuid", "")),
        "container_id": container_id,
        "container_image": container_image,
        "event_source": str(payload.get("source", "unknown")),
    }

# main.py 맨 아랫줄에 추가
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
