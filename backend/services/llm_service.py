import openai, os, json
from dotenv import load_dotenv

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")


def get_insight_only(rule: str, priority: str, output: str, cmdline: str) -> str:
    prompt = f"""컨테이너 보안 이벤트가 탐지되었습니다.
- Rule: {rule}
- Priority: {priority}
- Command: {cmdline}
- Output: {output}

이 이벤트가 왜 위험한지 한국어로 한 줄로 설명해주세요."""

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
    prompt = f"""You are a container runtime security analyst.

Falco detected the following security event:
- Rule: {rule}
- Priority: {priority}
- Command: {cmdline}
- Output: {output}

Top matching playbooks retrieved from the playbook VectorDB:
{examples}

Use the VectorDB similarity scores and approved actions as evidence. If the new event is close to
a stop playbook, recommend stop. If it is closer to an alert playbook, recommend alert. Use ignore
only when the event is clearly benign.

Respond in JSON only:
{{
  "action": "stop|alert|ignore",
  "insight": "한국어로 한 줄 설명",
  "playbook_reason": "VectorDB에서 검색된 어떤 playbook 사례를 근거로 삼았는지 한국어로 한 줄 설명"
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
