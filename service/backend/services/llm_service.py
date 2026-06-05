import openai, os, json
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


def get_insight_only(rule: str, priority: str, output: str, cmdline: str) -> str:
    prompt = f"""Assess this container security event.

Event:
 Rule: {rule}
 Priority: {priority}
 Command: {cmdline}

Output JSON only:
{{"insight": "한국어로 한 줄 설명"}}"""

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content.strip()


def _format_playbook_examples(playbook_examples: list[dict]) -> str:
    if not playbook_examples:
        return "- No approved playbook examples are available."

    lines = []
    for idx, playbook in enumerate(playbook_examples, start=1):
        lines.append(
            "\n".join([
                f"{idx}. Rule: {playbook.get('rule_name', '')}",
                f"   Approved action: {playbook.get('action', '')}",
                f"   Insight: {playbook.get('insight', '')}",
                f"   Approved by: {playbook.get('approved_by', '')}",
                f"   Similarity score: {playbook.get('similarity', 0):.3f}",
            ])
        )
    return "\n".join(lines)


def analyze_event(rule: str, priority: str, output: str, cmdline: str, playbook_examples: list[dict] | None = None) -> dict:
    examples = _format_playbook_examples(playbook_examples or [])
    prompt = f"""Assess this container security event and respond in JSON only.

Event:
 Rule: {rule}
 Priority: {priority}
 Command: {cmdline}

Similar playbook cases from VectorDB:
{examples}

Output JSON only:
{{
  "action": "stop|alert|ignore",
  "insight": "한국어로 한 줄 설명",
  "playbook_reason": "참고한 playbook 근거 한국어 한 줄"
}}"""

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"}
    )
    result = json.loads(response.choices[0].message.content)
    result["action"] = (result.get("action") or "alert").lower()
    if result["action"] not in {"stop", "alert", "ignore"}:
        result["action"] = "alert"
    return result
