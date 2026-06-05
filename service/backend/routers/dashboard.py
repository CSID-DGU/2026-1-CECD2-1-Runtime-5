from fastapi import APIRouter
from database import get_connection

router = APIRouter()


@router.get("/dashboard/summary")
def get_summary():
    conn = get_connection()
    total    = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    critical = conn.execute(
        "SELECT COUNT(*) FROM events WHERE UPPER(priority) IN ('CRITICAL','HIGH')"
    ).fetchone()[0]
    medium   = conn.execute(
        "SELECT COUNT(*) FROM events WHERE UPPER(priority) IN ('MEDIUM','WARNING')"
    ).fetchone()[0]
    low      = conn.execute("""
        SELECT COUNT(*) FROM events
        WHERE UPPER(COALESCE(priority, '')) NOT IN ('CRITICAL','HIGH','MEDIUM','WARNING')
    """).fetchone()[0]
    auto_actioned = conn.execute(
        "SELECT COUNT(*) FROM events WHERE UPPER(status) = 'AUTO_ACTIONED'"
    ).fetchone()[0]
    resolved = conn.execute(
        "SELECT COUNT(*) FROM events WHERE UPPER(status) = 'CONFIRMED'"
    ).fetchone()[0]
    rolled_back = conn.execute(
        "SELECT COUNT(*) FROM events WHERE UPPER(status) = 'ROLLED_BACK'"
    ).fetchone()[0]
    conn.close()
    return {
        "total": total,
        "critical": critical,
        "medium": medium,
        "low": low,
        "auto_actioned": auto_actioned,
        "resolved": resolved,
        "rolled_back": rolled_back,
    }


@router.get("/dashboard/timeline")
def get_timeline():
    conn = get_connection()
    rows = conn.execute("""
        SELECT substr(timestamp, 12, 5) as time, COUNT(*) as count
        FROM events
        GROUP BY substr(timestamp, 12, 5)
        ORDER BY time LIMIT 12
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]
