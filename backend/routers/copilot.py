import json
import os

import openai
from fastapi import APIRouter

from database import get_connection
from dotenv import load_dotenv
from routers.events import patch_decision
from time_utils import now_iso

load_dotenv()

router = APIRouter()
openai.api_key = os.getenv("OPENAI_API_KEY")


ACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "take_action",
        "description": "보안 이벤트에 대해 조치를 취한다",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {
                    "type": "string",
                    "description": "이벤트 ID (EV-XXXXXX 형식)",
                },
                "decision": {
                    "type": "string",
                    "enum": ["CONFIRMED", "ROLLED_BACK"],
                    "description": "승인 또는 롤백",
                },
                "manual_action": {
                    "type": "string",
                    "enum": ["stop", "alert", "ignore", "restart"],
                    "description": (
                        "관리자가 직접 지정하는 action. "
                        "stop=컨테이너중지, restart=컨테이너재시작, "
                        "alert=알림만, ignore=무시"
                    ),
                },
            },
            "required": ["event_id", "decision"],
        },
    },
}


def _get_event(event_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT id, rule_name, llm_action, status FROM events WHERE id = %s",
        (event_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def _format_action_reply(result: dict) -> str:
    if not result.get("ok"):
        return result.get("message", "이벤트 조치에 실패했습니다.")

    decision_label = "승인" if result["decision"] == "CONFIRMED" else "롤백"
    lines = [f"{result['event_id']} {decision_label} 완료"]
    if result.get("playbook_saved") and result.get("action"):
        lines.append(f"action: {result['action']} → playbook 저장됨")
    return "\n".join(lines)


def _take_action(arguments: dict) -> dict:
    event_id = arguments.get("event_id", "")
    decision = arguments.get("decision", "")
    manual_action = arguments.get("manual_action")

    event = _get_event(event_id)
    if not event:
        return {
            "ok": False,
            "event_id": event_id,
            "decision": decision,
            "manual_action": manual_action,
            "message": f"{event_id} 이벤트를 찾지 못했습니다.",
        }

    body = {"decision": decision}
    if manual_action:
        body["manual_action"] = manual_action

    patch_decision(event_id, body)
    saved_action = manual_action if decision == "ROLLED_BACK" else event["llm_action"]
    playbook_saved = decision == "CONFIRMED" or bool(manual_action)

    return {
        "ok": True,
        "event_id": event_id,
        "rule_name": event["rule_name"],
        "decision": decision,
        "manual_action": manual_action,
        "action": saved_action,
        "playbook_saved": playbook_saved,
        "message": _format_action_reply({
            "ok": True,
            "event_id": event_id,
            "decision": decision,
            "manual_action": manual_action,
            "action": saved_action,
            "playbook_saved": playbook_saved,
        }),
    }


def _normalize_action_arguments(message: str, arguments: dict) -> dict:
    normalized = dict(arguments)
    lowered = message.lower()

    if any(token in lowered for token in ["ignore", "무시"]):
        normalized["decision"] = "ROLLED_BACK"
        normalized["manual_action"] = "ignore"
    elif any(token in lowered for token in ["restart", "재시작", "다시 시작"]):
        normalized["decision"] = "ROLLED_BACK"
        normalized["manual_action"] = "restart"
    elif any(token in lowered for token in ["stop", "중지", "정지"]):
        normalized["decision"] = "ROLLED_BACK"
        normalized["manual_action"] = "stop"
    elif any(token in lowered for token in ["alert", "알림"]):
        normalized["decision"] = "ROLLED_BACK"
        normalized["manual_action"] = "alert"
    elif any(token in lowered for token in ["rollback", "롤백", "원상 복구", "원상복구"]):
        normalized["decision"] = "ROLLED_BACK"
    elif "승인" in lowered or "confirm" in lowered:
        normalized["decision"] = "CONFIRMED"
        normalized.pop("manual_action", None)

    return normalized


@router.post("/copilot/chat")
def post_chat(body: dict):
    message = body.get("message", "")

    conn = get_connection()
    recent = conn.execute(
        """
        SELECT id, rule_name, priority, status, llm_action, timestamp
        FROM events
        ORDER BY timestamp DESC
        LIMIT 20
        """
    ).fetchall()
    conn.close()

    context = "\n".join([
        f"- id={r['id']} | rule_name={r['rule_name']} | priority={r['priority']} | status={r['status']} | llm_action={r['llm_action']} | timestamp={r['timestamp']}"
        for r in recent
    ])

    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {
                "role": "system",
                "content": (
                    "당신은 컨테이너 보안 분석가입니다.\n"
                    "관리자가 이벤트 조치를 요청하면 take_action 함수를 호출하세요.\n"
                    "이벤트 목록이 필요하면 최근 이벤트를 알려주세요.\n"
                    "관리자가 특정 이벤트 ID를 언급하면 반드시 해당 ID를 이벤트 목록에서 찾아서 답변하세요.\n"
                    "목록에 없으면 없다고 말하지 말고 GET /api/v1/events에서 전체 조회해서 찾으세요.\n"
                    "'승인'은 decision=CONFIRMED로 처리하세요.\n"
                    "'rollback', '롤백', '원상 복구', '무시'는 decision=ROLLED_BACK로 처리하세요.\n"
                    "'무시'는 manual_action=ignore로 처리하세요.\n\n"
                    "'restart', '재시작', '다시 시작'은 manual_action=restart로 처리하세요.\n\n"
                    f"최근 탐지 이벤트:\n{context}"
                ),
            },
            {"role": "user",   "content": message}
        ],
        tools=[ACTION_TOOL],
    )
    response_message = response.choices[0].message
    action_result = None

    if response_message.tool_calls:
        for tool_call in response_message.tool_calls:
            if tool_call.function.name != "take_action":
                continue

            try:
                arguments = json.loads(tool_call.function.arguments or "{}")
            except json.JSONDecodeError:
                arguments = {}

            arguments = _normalize_action_arguments(message, arguments)
            action_result = _take_action(arguments)
            break

        reply = _format_action_reply(action_result) if action_result else "요청한 조치를 처리하지 못했습니다."
    else:
        reply = response_message.content or ""

    conn = get_connection()
    now = now_iso()
    conn.executemany("""
        INSERT INTO chat_messages (sender, message, created_at)
        VALUES (%s, %s, %s)
    """, [
        ("user", message, now),
        ("bot", reply, now),
    ])
    conn.commit()
    conn.close()

    return {"reply": reply, "action_result": action_result}


@router.get("/copilot/history")
def get_chat_history():
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, sender, message, created_at
        FROM chat_messages
        ORDER BY id DESC
        LIMIT 50
    """).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


@router.delete("/copilot/history")
def delete_chat_history():
    conn = get_connection()
    conn.execute("DELETE FROM chat_messages")
    conn.commit()
    conn.close()
    return {"ok": True}
