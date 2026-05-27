from fastapi import APIRouter
from database import get_connection
from services.playbook_service import get_playbook, get_similar_playbooks, save_playbook
from services.llm_service import analyze_event
from time_utils import now_iso

router = APIRouter()


@router.get("/events")
def get_events():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM events ORDER BY timestamp DESC LIMIT 50"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@router.get("/events/{event_id}")
def get_event_detail(event_id: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM events WHERE id = ?", (event_id,)
    ).fetchone()
    conn.close()
    if not row:
        return {"error": "not found"}
    return {
        "attackType": row["rule_name"],
        "aiInsight":  row["llm_insight"],
        "action":     row["llm_action"],
        "status":     row["status"],
    }


@router.post("/events/ingest")
def ingest_event(body: dict):
    conn = get_connection()
    conn.execute("""
        INSERT OR REPLACE INTO events
        (id, rule_name, priority, container, cmdline, output,
         llm_action, manual_action, llm_insight, from_playbook, status, timestamp)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        body["id"], body["rule_name"], body["priority"],
        body.get("container", ""), body.get("cmdline", ""),
        body.get("output", ""), body.get("llm_action", ""),
        body.get("manual_action", ""), body.get("llm_insight", ""),
        1 if body.get("from_playbook") else 0, body.get("status", "PENDING"),
        body.get("timestamp", now_iso())
    ))
    conn.commit()
    conn.close()
    return {"ok": True}


@router.patch("/events/{event_id}/decision")
def patch_decision(event_id: str, body: dict):
    decision = body.get("decision")
    manual_action = body.get("manual_action")
    conn = get_connection()

    if decision == "CONFIRMED":
        row = conn.execute(
            "SELECT * FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        if row:
            save_playbook(
                rule_name=row["rule_name"],
                action=row["llm_action"],
                insight=row["llm_insight"]
            )
        conn.execute(
            "UPDATE events SET status = 'CONFIRMED', manual_action = NULL WHERE id = ?", (event_id,)
        )
    elif decision == "ROLLED_BACK":
        if manual_action:
            row = conn.execute(
                "SELECT * FROM events WHERE id = ?", (event_id,)
            ).fetchone()
            if row:
                save_playbook(
                    rule_name=row["rule_name"],
                    action=manual_action,
                    insight=row["llm_insight"],
                    approved_by="security_engineer",
                )
        conn.execute(
            "UPDATE events SET status = 'ROLLED_BACK', manual_action = ? WHERE id = ?",
            (manual_action, event_id),
        )

    conn.commit()
    conn.close()
    return {"ok": True, "decision": decision, "manual_action": manual_action}


@router.post("/llm/analyze")
def llm_analyze(body: dict):
    rule     = body.get("rule", "")
    priority = body.get("priority", "")
    output   = body.get("output", "")
    cmdline  = body.get("cmdline", "")

    # 1. 플레이북 존재 → action + insight 모두 재사용, LLM 스킵
    playbook = get_playbook(rule)
    if playbook:
        return {
            "action":        playbook["action"],
            "insight":       playbook["insight"],
            "from_playbook": True,
            "approved_by":   playbook["approved_by"],
        }

    # 2. 정확 매칭 실패 → playbook VectorDB top-k 검색 결과를 근거로 LLM이 action 추천
    similar_playbooks = get_similar_playbooks(rule, output, cmdline)
    result = analyze_event(rule, priority, output, cmdline, similar_playbooks)
    return {
        **result,
        "from_playbook": False,
        "from_playbook_vectordb": True,
        "referenced_playbooks": [
            {
                "rule_name": item["rule_name"],
                "action": item["action"],
                "similarity": item["similarity"],
                "vector_distance": item["vector_distance"],
                "approved_by": item["approved_by"],
            }
            for item in similar_playbooks
        ],
    }


@router.get("/playbook")
def get_playbook_api(rule_name: str):
    playbook = get_playbook(rule_name)
    if not playbook:
        return {}
    return playbook


@router.get("/playbooks")
def get_playbooks():
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM playbooks ORDER BY created_at DESC, rule_name ASC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
