import os
import logging
import uuid

import httpx
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any
from time_utils import now_iso

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")
REMEDIATION_DRY_RUN = os.getenv("REMEDIATION_DRY_RUN", "true").lower() == "true"
REMEDIATION_ALLOWLIST = {"falco", "falcosidekick", "chroma", "backend", "bridge"}

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("bridge")

try:
    import docker
    from docker.errors import DockerException, NotFound
except ImportError as exc:
    docker = None
    DockerException = Exception
    NotFound = Exception
    logger.error("Docker SDK import failed; remediation disabled: %s", exc)

app = FastAPI()


class FalcoPayload(BaseModel):
    rule: Optional[str] = ""
    priority: Optional[str] = ""
    output: Optional[str] = ""
    output_fields: Optional[Dict[str, Any]] = {}
    source: Optional[str] = ""
    tags: Optional[list] = []


class RemediationPayload(BaseModel):
    container_name: Optional[str] = ""
    action: Optional[str] = "stop"


def _clean_container_value(value: Any) -> str:
    cleaned = str(value or "").strip().lstrip("/")
    if cleaned.lower() in {"", "<na>", "na", "n/a", "none", "null"}:
        return ""
    return cleaned


def _normalize_container_name(container_name: str | None) -> str:
    return _clean_container_value(container_name)


def _extract_container_target(output_fields: Dict[str, Any]) -> str:
    for key in ("container.name", "container.id", "containerID", "container_id"):
        value = _clean_container_value(output_fields.get(key))
        if value:
            return value
    return ""


def _is_allowlisted_container(container_name: str) -> bool:
    if container_name in REMEDIATION_ALLOWLIST:
        return True

    normalized = container_name.replace("_", "-")
    parts = normalized.rsplit("-", 2)
    return (
        len(parts) == 3
        and parts[1] in REMEDIATION_ALLOWLIST
        and parts[2].isdigit()
    )


def _remediate_container(container_name: str | None, action: str | None = "stop") -> dict:
    target = _normalize_container_name(container_name)
    remediation_action = str(action or "stop").lower()

    if not target:
        logger.info("Remediation skipped: empty container_name")
        return {"status": "skipped", "reason": "empty_container_name"}

    if remediation_action not in {"stop", "restart"}:
        logger.info("Remediation skipped: unsupported action %s", remediation_action)
        return {"status": "skipped", "reason": "unsupported_action"}

    if _is_allowlisted_container(target):
        logger.warning("Remediation skipped for allowlisted container: %s", target)
        return {"status": "skipped", "reason": "allowlist"}

    if docker is None:
        if REMEDIATION_DRY_RUN:
            logger.info("REMEDIATION_DRY_RUN=true; would %s container: %s", remediation_action, target)
            return {"status": "dry_run", "container": target, "action": remediation_action}

        logger.error("Docker SDK unavailable; cannot %s container: %s", remediation_action, target)
        return {"status": "error", "reason": "docker_sdk_unavailable"}

    try:
        client = docker.from_env()
        container = client.containers.get(target)
        resolved_name = _normalize_container_name(container.name)
        if _is_allowlisted_container(resolved_name):
            logger.warning("Remediation skipped for allowlisted container: %s", resolved_name)
            return {"status": "skipped", "reason": "allowlist"}

        if REMEDIATION_DRY_RUN:
            logger.info(
                "REMEDIATION_DRY_RUN=true; would %s container: %s",
                remediation_action,
                resolved_name or target,
            )
            return {
                "status": "dry_run",
                "container": resolved_name or target,
                "target": target,
                "action": remediation_action,
            }

        if remediation_action == "restart":
            container.restart()
            logger.info("Restarted container via remediation: %s", resolved_name or target)
            return {"status": "restarted", "container": resolved_name or target, "target": target}

        container.stop()
        logger.info("Stopped container via remediation: %s", resolved_name or target)
        return {"status": "stopped", "container": resolved_name or target, "target": target}
    except NotFound:
        logger.warning("Remediation target container not found: %s", target)
        return {"status": "not_found"}
    except DockerException as exc:
        logger.error("Docker remediation failed for %s: %s", target, exc)
        return {"status": "error", "reason": str(exc)}


@app.post("/remediate")
def remediate(payload: RemediationPayload):
    return _remediate_container(payload.container_name, payload.action)


@app.post("/webhook")
async def handle_falco_alert(payload: FalcoPayload):
    rule     = payload.rule or "Unknown"
    priority = payload.priority or "Debug"
    output   = payload.output or ""
    output_fields = payload.output_fields or {}
    cmdline  = str(output_fields.get("proc.cmdline", ""))
    container_name = _extract_container_target(output_fields)

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
        remediation_result = None
        if result.get("action") in {"stop", "restart"}:
            remediation_result = _remediate_container(container_name, result.get("action"))

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

    response = {"status": "success", "id": event_id}
    response["action"] = result.get("action")
    response["from_playbook"] = result.get("from_playbook", False)
    if remediation_result:
        response["remediation"] = remediation_result
    return response


@app.get("/status")
def status():
    return {"status": "ok", "backend_url": BACKEND_URL}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
