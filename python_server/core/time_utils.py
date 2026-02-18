import sqlite3
from datetime import datetime, date
from zoneinfo import ZoneInfo
import tzlocal

LOCAL_TZ = ZoneInfo(tzlocal.get_localzone_name())

# ---------------------------------------------------------------------------
# SQLite adapters / converters (Python 3.12+ deprecation fix)
# Must run once at process level before any engine is created.
# ---------------------------------------------------------------------------
sqlite3.register_adapter(datetime, lambda val: val.isoformat())
sqlite3.register_adapter(date, lambda val: val.isoformat())
sqlite3.register_converter("timestamp", lambda b: datetime.fromisoformat(b.decode()))
sqlite3.register_converter("date", lambda b: date.fromisoformat(b.decode()))


def now():
    """Return timezone-aware current datetime using system local timezone."""
    return datetime.now(LOCAL_TZ)


def sqlite_connect_args() -> dict:
    """Return connect_args dict that enables SQLite type detection."""
    return {"detect_types": sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES}
