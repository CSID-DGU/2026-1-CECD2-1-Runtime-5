# LLM 프롬프트 생성 — 응답 형식 JSON 강제

import os

def build_prompt(payload: dict) -> str:
    version   = os.getenv("PROMPT_VERSION", "v1").lower()
    rule      = payload.get("rule", "unknown")
    priority  = payload.get("priority", "unknown")
    fields    = payload.get("output_fields", {}) or {}
    cmdline   = fields.get("proc.cmdline", "unknown")

    if version == "v3":
        # 초압축 프롬프트 (V3) - 토큰 극소화
        return f"Task: Container Sec. Output: {{\"a\":\"stop|pause|alert|ignore\",\"t\":\"h|m|l|n\",\"r\":\"str\"}}\nEvt: R:{rule},P:{priority},C:{cmdline}"

    elif version == "v2":
        # 압축된 프롬프트 (V2) - 불필요 자연어 제거, 핵심 필드만 전달
        return f"""Task: Assess container security threat. Output JSON only: {{"action": "stop|pause|alert|ignore", "threat_level": "high|medium|low|none", "reason": "str"}}
Action Rules: stop(terminate), pause(investigate), alert(notify), ignore(normal).
Event:
 Rule: {rule}
 Priority: {priority}
 Command: {cmdline}"""

    else:
        # 기존 프롬프트 (V1) - 전체 자연어 및 output 포함
        output    = payload.get("output", "")
        container = fields.get("container.name", "unknown")
        
        return f"""You are a container runtime security analyst.

Falco detected the following security event:
- Rule: {rule}
- Priority: {priority}
- Container: {container}
- Command: {cmdline}
- Output: {output}

Based on the above, determine the appropriate response.

Respond in JSON only (no explanation outside JSON):
{{
  "action": "stop|pause|alert|ignore",
  "threat_level": "high|medium|low|none",
  "reason": "one sentence explanation"
}}

Rules:
- stop: container must be immediately terminated
- pause: container should be suspended for investigation
- alert: log and notify, no container action needed
- ignore: normal behavior, no action needed"""
