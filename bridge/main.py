import os
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from time_utils import now_iso

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")

app = FastAPI()


class FalcoPayload(BaseModel):
    rule: Optional[str] = ""
    priority: Optional[str] = ""
    output: Optional[str] = ""
    output_fields: Optional[Dict[str, Any]] = {}
    source: Optional[str] = ""
    tags: Optional[list] = []


@app.post("/webhook")
async def handle_falco_alert(payload: FalcoPayload):
    rule     = payload.rule or "Unknown"
    priority = payload.priority or "Debug"
    output   = payload.output or ""
    output_fields = payload.output_fields or {}
    cmdline  = str(output_fields.get("proc.cmdline", ""))
    container_name = str(output_fields.get("container.name", ""))

    async with httpx.AsyncClient() as client:
        # Step 1: LLM 분석
        llm_resp = await client.post(
            f"{BACKEND_URL}/api/v1/llm/analyze",
            json={
                "rule":     rule,
                "priority": priority,
                "output":   output,
                "cmdline":  cmdline,
            },
            timeout=30.0,
        )
        if llm_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"LLM analyze failed: {llm_resp.text}")

        result = llm_resp.json()

        # Step 2: 이벤트 저장
        event_id = "EV-" + uuid.uuid4().hex[:6].upper()
        ingest_resp = await client.post(
            f"{BACKEND_URL}/api/v1/events/ingest",
            json={
                "id":          event_id,
                "rule_name":   rule,
                "priority":    priority,
                "container":   container_name,
                "cmdline":     cmdline,
                "output":      output,
                "llm_action":  result.get("action"),
                "llm_insight": result.get("insight"),
                "from_playbook": result.get("from_playbook", False),
                "status":      "AUTO_ACTIONED",
                "timestamp":   now_iso(),
            },
            timeout=10.0,
        )
        if ingest_resp.status_code != 200:
            raise HTTPException(status_code=502, detail=f"Event ingest failed: {ingest_resp.text}")

    return {"status": "success", "id": event_id}


@app.get("/status")
def status():
    return {"status": "ok", "backend_url": BACKEND_URL}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
