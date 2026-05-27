import os

import chromadb
import openai
from dotenv import load_dotenv

from database import get_connection
from time_utils import now_iso

load_dotenv()

openai.api_key = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
CHROMA_HOST = os.getenv("CHROMA_HOST", "localhost")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
CHROMA_COLLECTION = os.getenv("CHROMA_COLLECTION", "runtime_playbooks")


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


def _collection():
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return client.get_or_create_collection(
        name=CHROMA_COLLECTION,
        metadata={"hnsw:space": "cosine"},
    )


def _upsert_playbook_vector(playbook: dict):
    source_text = _playbook_source_text(playbook)
    collection = _collection()
    collection.upsert(
        ids=[playbook["rule_name"]],
        embeddings=[_embed_text(source_text)],
        documents=[source_text],
        metadatas=[{
            "rule_name": playbook["rule_name"],
            "action": playbook.get("action", ""),
            "insight": playbook.get("insight", ""),
            "approved_by": playbook.get("approved_by", ""),
            "created_at": playbook.get("created_at") or "",
            "embedding_model": EMBEDDING_MODEL,
            "updated_at": now_iso(),
        }],
    )


def sync_playbook_vectors():
    conn = get_connection()
    rows = conn.execute("""
        SELECT rule_name, action, insight, approved_by, created_at
        FROM playbooks
        ORDER BY created_at DESC, rule_name ASC
    """).fetchall()
    conn.close()

    collection = _collection()
    for row in rows:
        playbook = dict(row)
        source_text = _playbook_source_text(playbook)
        collection.upsert(
            ids=[playbook["rule_name"]],
            embeddings=[_embed_text(source_text)],
            documents=[source_text],
            metadatas=[{
                "rule_name": playbook["rule_name"],
                "action": playbook.get("action", ""),
                "insight": playbook.get("insight", ""),
                "approved_by": playbook.get("approved_by", ""),
                "created_at": playbook.get("created_at") or "",
                "embedding_model": EMBEDDING_MODEL,
                "updated_at": now_iso(),
            }],
        )


def get_playbook(rule_name: str):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM playbooks WHERE rule_name = ?", (rule_name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_similar_playbooks(rule_name: str, output: str = "", cmdline: str = "", limit: int = 5):
    sync_playbook_vectors()

    query_embedding = _embed_text(_event_source_text(rule_name, output, cmdline))
    results = _collection().query(
        query_embeddings=[query_embedding],
        n_results=limit,
        include=["documents", "metadatas", "distances"],
    )

    ids = results.get("ids", [[]])[0]
    metadatas = results.get("metadatas", [[]])[0]
    documents = results.get("documents", [[]])[0]
    distances = results.get("distances", [[]])[0]

    playbooks = []
    for idx, metadata in enumerate(metadatas):
        distance = distances[idx] if idx < len(distances) else 1.0
        playbooks.append({
            "rule_name": metadata.get("rule_name") or ids[idx],
            "action": metadata.get("action", ""),
            "insight": metadata.get("insight", ""),
            "approved_by": metadata.get("approved_by", ""),
            "created_at": metadata.get("created_at", ""),
            "source_text": documents[idx] if idx < len(documents) else "",
            "similarity": max(0.0, 1.0 - float(distance)),
            "vector_distance": float(distance),
        })
    return playbooks


def save_playbook(rule_name: str, action: str, insight: str, approved_by: str = "security_engineer"):
    now = now_iso()
    conn = get_connection()
    conn.execute("""
        INSERT INTO playbooks
        (rule_name, action, insight, approved_by, created_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(rule_name) DO UPDATE SET
            action = excluded.action,
            insight = excluded.insight,
            approved_by = excluded.approved_by,
            created_at = excluded.created_at
    """, (rule_name, action, insight, approved_by, now))
    conn.commit()

    row = conn.execute(
        "SELECT rule_name, action, insight, approved_by, created_at FROM playbooks WHERE rule_name = ?",
        (rule_name,)
    ).fetchone()
    conn.close()

    if row:
        _upsert_playbook_vector(dict(row))
