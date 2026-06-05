import datetime

KST = datetime.timezone(datetime.timedelta(hours=9), "KST")


def now_iso() -> str:
    return datetime.datetime.now(KST).isoformat()
