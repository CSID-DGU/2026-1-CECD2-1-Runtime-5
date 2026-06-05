# LLM 프롬프트 생성 — 응답 형식 JSON 강제

def build_prompt(payload: dict) -> str:
    rule      = payload.get("rule", "unknown")
    priority  = payload.get("priority", "unknown")
    output    = payload.get("output", "")
    fields    = payload.get("output_fields", {}) or {}
    container = fields.get("container.name", "unknown")
    cmdline   = fields.get("proc.cmdline", "unknown")

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
