import csv
import os
import datetime
import json
import time
import re
import sqlite3
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
DB_FILE = os.path.join(DATA_DIR, "llm_cache.db")
OLLAMA_URL = "http://ollama:11434/api/generate"
remediator = DockerRemediator()

os.makedirs(DATA_DIR, exist_ok=True)

# --- SQLite 초기화 ---
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS cache 
                 (normalized_log TEXT PRIMARY KEY, score INTEGER, reason TEXT, 
                  p_tokens INTEGER, c_tokens INTEGER)''')
    conn.commit()
    conn.close()

init_db()

def get_cached_result(normalized_log):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT score, reason FROM cache WHERE normalized_log=?", (normalized_log,))
    row = c.fetchone()
    conn.close()
    return row

def save_to_cache(normalized_log, score, reason, p, c):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO cache VALUES (?, ?, ?, ?, ?)", 
                   (normalized_log, score, reason, p, c))
    conn.commit()
    conn.close()

# --- 로그 정규화 함수 ---
def normalize_log(text: str) -> str:
    """로그에서 가변적인 값(HEX 주소, PID, 경로 내 숫자)을 제거하여 캐시 효율 증대"""
    text = re.sub(r"0x[0-9a-fA-F]+", "[HEX]", text) # Hex 주소
    text = re.sub(r"\b\d+\b", "[ID]", text)       # 숫자(PID 등)
    text = re.sub(r"(/[a-zA-Z0-9._-]+)+", "[PATH]", text) # 경로 단순화 (선택적)
    return text.strip()

# CSV 초기화
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, mode='w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "event_type", "rule_name", "priority", "prompt_tokens", "completion_tokens", "latency_ms", "remediation_status", "remediation_action", "mitre_technique", "target_container", "attack_source", "attack_label", "attack_id", "container_id", "container_image", "event_source", "is_cached"])

@app.post("/webhook")
async def handle_falco_alert(request: Request):
    start_time = time.time()
    payload = await request.json()
    
    rule_name = payload.get("rule", "Unknown")
    priority = payload.get("priority", "Debug")
    output = payload.get("output", "")
    correlation = extract_correlation_fields(payload)
    
    remediation_result = remediator.remediate(payload)
    status = remediation_result.get("status", "unknown")
    
    event_type = "Rule-based"
    p_tokens, c_tokens, is_cached = 0, 0, 0

    if status == "ignored":
        event_type = "LLM-analyzed"
        norm_log = normalize_log(output)
        cached = get_cached_result(norm_log)
        
        if cached:
            is_cached = 1
        else:
            async with httpx.AsyncClient() as client:
                # 최적화된 프롬프트: JSON 출력 강제하여 출력 토큰 절약
                prompt = f"Analyze Falco log. Return ONLY JSON {{'score':0-10, 'reason':'1sentence'}}. Log: {norm_log}"
                try:
                    resp = await client.post(OLLAMA_URL, json={
                        "model": "qwen2.5:0.5b",
                        "prompt": prompt,
                        "stream": False,
                        "format": "json" # Ollama에서 JSON 출력을 보장하는 옵션
                    }, timeout=15.0)
                    res_json = resp.json()
                    p_tokens = res_json.get("prompt_eval_count", 0)
                    c_tokens = res_json.get("eval_count", 0)
                    
                    # 결과 파싱 및 저장 (간소화)
                    llm_data = json.loads(res_json.get("response", "{}"))
                    save_to_cache(norm_log, llm_data.get("score", 0), llm_data.get("reason", ""), p_tokens, c_tokens)
                except Exception as e:
                    print(f"LLM Error: {e}")

    latency = int((time.time() - start_time) * 1000)

    with open(CSV_FILE, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([datetime.datetime.now().isoformat(), event_type, rule_name, priority, p_tokens, c_tokens, latency, status, remediation_result.get("action", ""), remediation_result.get("mitre", {}).get("technique_id", ""), remediation_result.get("target", ""), correlation["attack_source"], correlation["attack_label"], correlation["attack_id"], correlation["container_id"], correlation["container_image"], correlation["event_source"], is_cached])

    return {"status": "success", "cached": bool(is_cached)}

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
