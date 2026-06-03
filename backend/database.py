import os

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import DictCursor

from time_utils import now_iso

load_dotenv()

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://runtime:runtime1234@localhost:5432/runtime_security",
)


class PgConnection:
    def __init__(self):
        self._conn = psycopg2.connect(DATABASE_URL, cursor_factory=DictCursor)

    def cursor(self):
        return self._conn.cursor()

    def execute(self, query, params=None):
        cur = self.cursor()
        cur.execute(query, params)
        return cur

    def executemany(self, query, params=None):
        cur = self.cursor()
        cur.executemany(query, params)
        return cur

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()

    def __getattr__(self, name):
        return getattr(self._conn, name)


def get_connection():
    return PgConnection()


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("CREATE EXTENSION IF NOT EXISTS vector")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id            TEXT PRIMARY KEY,
            rule_name     TEXT NOT NULL,
            priority      TEXT,
            container     TEXT,
            cmdline       TEXT,
            output        TEXT,
            llm_action    TEXT,
            manual_action TEXT,
            llm_insight   TEXT,
            from_playbook BOOLEAN DEFAULT FALSE,
            status        TEXT DEFAULT 'PENDING',
            timestamp     TEXT
        )
    """)

    cur.execute("""
        ALTER TABLE events
        ADD COLUMN IF NOT EXISTS manual_action TEXT
    """)
    cur.execute("""
        ALTER TABLE events
        ADD COLUMN IF NOT EXISTS from_playbook BOOLEAN DEFAULT FALSE
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS playbooks (
            rule_name       TEXT PRIMARY KEY,
            action          TEXT NOT NULL,
            insight         TEXT,
            approved_by     TEXT DEFAULT 'security_engineer',
            created_at      TEXT,
            source_text     TEXT,
            embedding       vector(1536),
            embedding_model TEXT,
            updated_at      TEXT
        )
    """)

    cur.execute("""
        ALTER TABLE playbooks
        ADD COLUMN IF NOT EXISTS source_text TEXT
    """)
    cur.execute("""
        ALTER TABLE playbooks
        ADD COLUMN IF NOT EXISTS embedding vector(1536)
    """)
    cur.execute("""
        ALTER TABLE playbooks
        ADD COLUMN IF NOT EXISTS embedding_model TEXT
    """)
    cur.execute("""
        ALTER TABLE playbooks
        ADD COLUMN IF NOT EXISTS updated_at TEXT
    """)

    cur.execute("""
        CREATE INDEX IF NOT EXISTS playbooks_embedding_hnsw_idx
        ON playbooks USING hnsw (embedding vector_cosine_ops)
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id SERIAL PRIMARY KEY,
            sender TEXT NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT
        )
    """)

    conn.commit()
    conn.close()

    seed_playbooks()


def seed_playbooks():
    default_playbooks = [
        (
            "Drop and execute new binary in container",
            "stop",
            "컨테이너 내 임의 바이너리 실행 — 즉각 중단 필요",
        ),
        (
            "Run shell untrusted",
            "stop",
            "신뢰되지 않은 쉘 실행 — 즉각 차단 필요",
        ),
        (
            "Netcat Remote Code Execution in Container",
            "stop",
            "netcat 기반 원격 코드 실행 시도 탐지",
        ),
        (
            "PTRACE attached to process",
            "stop",
            "ptrace를 통한 프로세스 권한 탈취 시도",
        ),
        (
            "Read sensitive file untrusted",
            "alert",
            "신뢰되지 않은 프로세스의 민감 파일 접근",
        ),
    ]

    conn = get_connection()
    cur = conn.cursor()
    cur.executemany("""
        INSERT INTO playbooks
        (rule_name, action, insight, approved_by, created_at)
        VALUES (%s, %s, %s, 'system', %s)
        ON CONFLICT (rule_name) DO NOTHING
    """, [
        (rule, action, insight, now_iso())
        for rule, action, insight in default_playbooks
    ])
    cur.executemany("""
        UPDATE playbooks
        SET approved_by = 'system'
        WHERE rule_name = %s
    """, [
        (rule,)
        for rule, _, _ in default_playbooks
    ])
    conn.commit()
    conn.close()
