import os

import openai
from dotenv import load_dotenv

from database import get_connection
from time_utils import now_iso

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


def _playbook_source_text(playbook: dict) -> str:
    return "\n".join([
        f"Rule: {playbook.get('rule_name', '')}",
        f"Approved action: {playbook.get('action', '')}",
        f"Insight: {playbook.get('insight', '')}",
        f"Approved by: {playbook.get('approved_by', '')}",
    ])


def _event_source_text(rule_name: str, output: str = "", cmdline: str = "") -> str:
    return "\n".join([
        f"Rule: {rule_name}",
        f"Command: {cmdline}",
        f"Output: {output}",
    ])


def _embed_text(text: str) -> list[float]:
    response = openai.embeddings.create(
        model=EMBEDDING_MODEL,
        input=text,
    )
    return response.data[0].embedding


def _vector_literal(embedding: list[float]) -> str:
    return "[" + ",".join(str(value) for value in embedding) + "]"


def _upsert_playbook_vector(playbook: dict):
    source_text = _playbook_source_text(playbook)
    embedding = _vector_literal(_embed_text(source_text))

    conn = get_connection()
    conn.execute("""
        UPDATE playbooks
        SET source_text = %s,
            embedding = %s::vector,
            embedding_model = %s,
            updated_at = %s
        WHERE rule_name = %s
    """, (
        source_text,
        embedding,
        EMBEDDING_MODEL,
        now_iso(),
        playbook["rule_name"],
    ))
    conn.commit()
    conn.close()


def sync_playbook_vectors():
    conn = get_connection()
    rows = conn.execute("""
        SELECT rule_name, action, insight, approved_by, created_at
        FROM playbooks
        WHERE embedding IS NULL OR embedding_model IS DISTINCT FROM %s
        ORDER BY created_at DESC, rule_name ASC
    """, (EMBEDDING_MODEL,)).fetchall()
    conn.close()

    for row in rows:
        _upsert_playbook_vector(dict(row))


def get_playbook(rule_name: str):
    conn = get_connection()
    row = conn.execute(
        """
        SELECT rule_name, action, insight, approved_by, created_at
        FROM playbooks
        WHERE rule_name = %s
        """,
        (rule_name,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_similar_playbooks(rule_name: str, output: str = "", cmdline: str = "", limit: int = 5):
    sync_playbook_vectors()

    query_embedding = _vector_literal(_embed_text(_event_source_text(rule_name, output, cmdline)))
    conn = get_connection()
    rows = conn.execute("""
        SELECT rule_name,
               action,
               insight,
               approved_by,
               created_at,
               source_text,
               embedding <=> %s::vector AS vector_distance
        FROM playbooks
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> %s::vector
        LIMIT %s
    """, (query_embedding, query_embedding, limit)).fetchall()
    conn.close()

    playbooks = []
    for row in rows:
        distance = float(row["vector_distance"])
        playbooks.append({
            "rule_name": row["rule_name"],
            "action": row["action"] or "",
            "insight": row["insight"] or "",
            "approved_by": row["approved_by"] or "",
            "created_at": row["created_at"] or "",
            "source_text": row["source_text"] or "",
            "similarity": max(0.0, 1.0 - distance),
            "vector_distance": distance,
        })
    return playbooks


def save_playbook(rule_name: str, action: str, insight: str, approved_by: str = "security_engineer"):
    now = now_iso()
    conn = get_connection()
    conn.execute("""
        INSERT INTO playbooks
        (rule_name, action, insight, approved_by, created_at)
        VALUES (%s, %s, %s, %s, %s)
        ON CONFLICT(rule_name) DO UPDATE SET
            action = excluded.action,
            insight = excluded.insight,
            approved_by = excluded.approved_by,
            created_at = excluded.created_at,
            embedding = NULL,
            embedding_model = NULL,
            updated_at = NULL
    """, (rule_name, action, insight, approved_by, now))
    conn.commit()

    row = conn.execute(
        "SELECT rule_name, action, insight, approved_by, created_at FROM playbooks WHERE rule_name = %s",
        (rule_name,)
    ).fetchone()
    conn.close()

    if row:
        _upsert_playbook_vector(dict(row))
