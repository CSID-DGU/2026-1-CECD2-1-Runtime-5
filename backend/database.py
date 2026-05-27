import sqlite3, os
from dotenv import load_dotenv
from time_utils import now_iso

load_dotenv()

DB_PATH = os.getenv("DATABASE_URL", "./runtime.db")


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id          TEXT PRIMARY KEY,
            rule_name   TEXT NOT NULL,
            priority    TEXT,
            container   TEXT,
            cmdline     TEXT,
            output      TEXT,
            llm_action  TEXT,
            manual_action TEXT,
            llm_insight TEXT,
            from_playbook INTEGER DEFAULT 0,
            status      TEXT DEFAULT 'PENDING',
            timestamp   TEXT
        )
    """)

    existing_event_columns = {
        row[1]
        for row in cur.execute("PRAGMA table_info(events)").fetchall()
    }
    if "manual_action" not in existing_event_columns:
        cur.execute("ALTER TABLE events ADD COLUMN manual_action TEXT")
    if "from_playbook" not in existing_event_columns:
        cur.execute("ALTER TABLE events ADD COLUMN from_playbook INTEGER DEFAULT 0")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS playbooks (
            rule_name   TEXT PRIMARY KEY,
            action      TEXT NOT NULL,
            insight     TEXT,
            approved_by TEXT DEFAULT 'security_engineer',
            created_at  TEXT
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
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
    conn.executemany("""
        INSERT OR IGNORE INTO playbooks
        (rule_name, action, insight, approved_by, created_at)
        VALUES (?, ?, ?, 'system', ?)
    """, [
        (rule, action, insight, now_iso())
        for rule, action, insight in default_playbooks
    ])
    conn.executemany("""
        UPDATE playbooks
        SET approved_by = 'system'
        WHERE rule_name = ?
    """, [
        (rule,)
        for rule, _, _ in default_playbooks
    ])
    conn.commit()
    conn.close()
