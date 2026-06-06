# playbook 자동 대응 엔진 — 5개 핵심 위협만 매핑, 나머지는 LLM으로 라우팅

import os
from dataclasses import dataclass
from typing import Any

import docker
from docker.errors import APIError, DockerException, NotFound


@dataclass(frozen=True)
class RemediationDecision:
    technique_id: str
    technique_name: str
    action: str
    reason: str


class DockerRemediator:
    def __init__(self) -> None:
        self.enabled = os.getenv("ENABLE_REMEDIATION", "true").lower() == "true"
        self.dry_run = os.getenv("REMEDIATION_DRY_RUN", "false").lower() == "true"
        self.exclude_containers = {
            name.strip()
            for name in os.getenv("REMEDIATION_EXCLUDE", "falco,falcosidekick,python-bridge,ollama").split(",")
            if name.strip()
        }
        self.client = None
        if self.enabled:
            try:
                self.client = docker.from_env()
            except DockerException:
                self.client = None

    def remediate(self, payload: dict[str, Any]) -> dict[str, Any]:
        decision = self._classify(payload)
        if not decision:
            return {"status": "ignored", "reason": "No MITRE mapping matched"}

        container_id = self._extract_container_id(payload)
        container_name = self._extract_container_name(payload)
        target = container_name or container_id or "unknown"

        if not container_id:
            return {
                "status": "skipped",
                "reason": "Container ID not found in Falco event",
                "target": target,
                "mitre": decision.__dict__,
            }

        if container_name and container_name in self.exclude_containers:
            return {
                "status": "skipped",
                "reason": f"Container '{container_name}' is allowlisted",
                "target": container_name,
                "mitre": decision.__dict__,
            }

        if not self.enabled:
            return {
                "status": "disabled",
                "reason": "Remediation engine disabled",
                "target": target,
                "action": decision.action,
                "mitre": decision.__dict__,
            }

        if self.dry_run:
            return {
                "status": "dry-run",
                "reason": decision.reason,
                "target": target,
                "action": decision.action,
                "mitre": decision.__dict__,
            }

        if not self.client:
            return {
                "status": "error",
                "reason": "Docker client unavailable",
                "target": target,
                "mitre": decision.__dict__,
            }

        try:
            container = self.client.containers.get(container_id)
            resolved_name = self._normalize_container_name(container.name)
            if resolved_name in self.exclude_containers:
                return {
                    "status": "skipped",
                    "reason": f"Container '{resolved_name}' is allowlisted",
                    "target": resolved_name,
                    "mitre": decision.__dict__,
                }

            if decision.action == "pause":
                container.pause()
            elif decision.action == "stop":
                container.stop(timeout=5)
            elif decision.action == "alert":
                # docker 조작 없이 로그 기록만
                return {
                    "status": "alerted",
                    "reason": decision.reason,
                    "target": resolved_name,
                    "action": decision.action,
                    "mitre": decision.__dict__,
                }
            else:
                return {
                    "status": "error",
                    "reason": f"Unsupported action '{decision.action}'",
                    "target": resolved_name,
                    "mitre": decision.__dict__,
                }

            return {
                "status": "executed",
                "reason": decision.reason,
                "target": resolved_name,
                "action": decision.action,
                "mitre": decision.__dict__,
            }
        except NotFound:
            return {
                "status": "error",
                "reason": f"Container '{container_id}' not found",
                "target": target,
                "mitre": decision.__dict__,
            }
        except (APIError, DockerException) as exc:
            return {
                "status": "error",
                "reason": str(exc),
                "target": target,
                "mitre": decision.__dict__,
            }

    def _classify(self, payload: dict[str, Any]) -> RemediationDecision | None:
        rule_name = str(payload.get("rule", "")).lower()
        output    = str(payload.get("output", "")).lower()

        # 룰 매칭 맵: (부분 문자열, 대응 정보)
        PLAYBOOK_MAP = [
            ("drop and execute new binary in container", RemediationDecision(
                technique_id="T1485", technique_name="Data Destruction",
                action="stop", reason="New binary dropped and executed inside container"
            )),
            ("run shell untrusted", RemediationDecision(
                technique_id="T1059", technique_name="Command and Scripting Interpreter",
                action="stop", reason="Untrusted shell execution detected inside container"
            )),
            ("netcat remote code execution in container", RemediationDecision(
                technique_id="T1059", technique_name="Command and Scripting Interpreter",
                action="stop", reason="Netcat-based remote code execution detected inside container"
            )),
            ("ptrace attached to process", RemediationDecision(
                technique_id="T1068", technique_name="Exploitation for Privilege Escalation",
                action="stop", reason="ptrace attach detected — possible privilege escalation attempt"
            )),
            ("read sensitive file untrusted", RemediationDecision(
                technique_id="T1083", technique_name="File and Directory Discovery",
                action="alert", reason="Sensitive file read by untrusted process"
            )),
        ]

        for pattern, decision in PLAYBOOK_MAP:
            if pattern in rule_name or pattern in output:
                return decision

        return None

    @staticmethod
    def _extract_container_id(payload: dict[str, Any]) -> str | None:
        output_fields = payload.get("output_fields", {}) or {}
        for key in ("container.id", "containerID", "container_id"):
            value = output_fields.get(key) or payload.get(key)
            if value:
                return str(value)
        return None

    @staticmethod
    def _extract_container_name(payload: dict[str, Any]) -> str | None:
        output_fields = payload.get("output_fields", {}) or {}
        for key in ("container.name", "container_name"):
            value = output_fields.get(key) or payload.get(key)
            if value:
                return DockerRemediator._normalize_container_name(str(value))
        return None

    @staticmethod
    def _normalize_container_name(name: str) -> str:
        return name.lstrip("/")
