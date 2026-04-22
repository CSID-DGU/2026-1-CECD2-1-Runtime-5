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
        if decision == "safe":
            return {"status": "safe", "reason": "Known safe system activity"}
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

    def _classify(self, payload: dict[str, Any]) -> RemediationDecision | str | None:
        rule_name = str(payload.get("rule", "")).lower()
        output = str(payload.get("output", "")).lower()
        priority = str(payload.get("priority", "")).lower()

        # [추가] 명백히 안전한 정상 시스템 활동 (LLM 전송 방지)
        safe_rules = ["package management process", "read shell configuration file", "linux kernel version", "system uptime", "process status"]
        if any(r in rule_name for r in safe_rules):
            return "safe"

        if "terminal shell in container" in rule_name or "terminal shell in container" in output:
            return RemediationDecision(
                technique_id="T1059",
                technique_name="Command and Scripting Interpreter",
                action="stop",
                reason="Interactive shell execution detected inside container",
            )

        # [추가] 민감 파일 접근 탐지
        sensitive_files = ["/etc/shadow", "/etc/passwd", "/root/.ssh", "id_rsa"]
        if any(f in output for f in sensitive_files):
            return RemediationDecision(
                technique_id="T1555",
                technique_name="Credentials from Password Stores",
                action="stop",
                reason="Access to sensitive credential files detected",
            )

        # [추가] 공격 도구 및 네트워크 스캔 탐지
        attack_tools = ["nmap ", "netcat ", "nc -", "sqlmap", "ncat "]
        if any(tool in output for tool in attack_tools):
            return RemediationDecision(
                technique_id="T1595",
                technique_name="Active Scanning",
                action="pause",
                reason="Known attack or scanning tool detected",
            )

        # [추가] 로그 삭제 시도 탐지
        if "rm " in output and "/var/log" in output:
            return RemediationDecision(
                technique_id="T1070",
                technique_name="Indicator Removal",
                action="stop",
                reason="Attempt to clear system logs detected",
            )

        if "codex e2e shell trigger" in rule_name or "codex e2e shell trigger" in output:
            return RemediationDecision(
                technique_id="T1059",
                technique_name="Command and Scripting Interpreter",
                action="stop",
                reason="Deterministic shell trigger detected inside container",
            )

        if "write below binary dir" in rule_name or "write below binary dir" in output:
            return RemediationDecision(
                technique_id="T1574",
                technique_name="Hijack Execution Flow",
                action="stop",
                reason="Binary path modification detected inside container",
            )

        if "modify shell configuration file" in rule_name or "modify shell configuration file" in output:
            return RemediationDecision(
                technique_id="T1546",
                technique_name="Event-Triggered Execution",
                action="pause",
                reason="Persistence-related shell profile modification detected",
            )

        if "contact k8s api server from container" in rule_name or "contact k8s api server from container" in output:
            return RemediationDecision(
                technique_id="T1526",
                technique_name="Cloud Service Discovery",
                action="pause",
                reason="Unexpected control-plane discovery attempt from container",
            )

        if priority == "critical":
            return RemediationDecision(
                technique_id="T1485",
                technique_name="Data Destruction",
                action="stop",
                reason="Critical-severity Falco event received",
            )

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
