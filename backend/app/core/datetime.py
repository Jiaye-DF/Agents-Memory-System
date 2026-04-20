from datetime import datetime
from zoneinfo import ZoneInfo

TAIPEI_TZ = ZoneInfo("Asia/Taipei")


def to_taipei_iso(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(TAIPEI_TZ).isoformat()
