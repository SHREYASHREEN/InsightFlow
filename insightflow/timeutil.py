"""All timestamps are stored as naive UTC ISO strings 'YYYY-MM-DD HH:MM:SS'.
SLA maths use calendar hours (24x7, weekends included) - see docs/KPI_FORMULAS.md."""
from datetime import datetime, timedelta, timezone

FMT = "%Y-%m-%d %H:%M:%S"


def now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)


def to_str(dt):
    return dt.strftime(FMT)


def parse(value):
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip().replace("T", " ")
    for fmt in (FMT, "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date/time: {value!r}")


def hours_between(a, b):
    return (b - a).total_seconds() / 3600.0
