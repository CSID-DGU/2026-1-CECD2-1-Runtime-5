import csv
import io

from fastapi import APIRouter
from fastapi.responses import Response

from database import get_connection

router = APIRouter()


@router.get("/reports/export")
def export_report():
    conn = get_connection()
    rows = conn.execute("""
        SELECT id, timestamp, priority, rule_name, container,
               cmdline, status, llm_action, manual_action,
               llm_insight, from_playbook, output
        FROM events
        ORDER BY timestamp DESC
    """).fetchall()
    conn.close()

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow([
        "id",
        "timestamp",
        "priority",
        "rule_name",
        "container",
        "cmdline",
        "status",
        "llm_action",
        "manual_action",
        "llm_insight",
        "from_playbook",
        "output",
    ])
    for row in rows:
        writer.writerow([row[column] for column in row.keys()])

    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="security_report.csv"'
        },
    )
