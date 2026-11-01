"""China-timezone helpers.

Public content is published for a Chinese audience, so every day boundary
(quota windows, daily quotes, discovery buckets) must be computed in
``Asia/Shanghai`` instead of the host machine's local timezone.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo


CHINA_TIMEZONE = ZoneInfo("Asia/Shanghai")


def now_cn() -> datetime:
    """Current timezone-aware time in Asia/Shanghai."""
    return datetime.now(CHINA_TIMEZONE)


def today_cn() -> date:
    """Current calendar date in Asia/Shanghai."""
    return now_cn().date()


def day_start_cn(day: date | None = None) -> datetime:
    """Naive Shanghai midnight for ``day``.

    Stored timestamps are naive local (Shanghai) datetimes, so quota windows
    are compared against naive values.
    """
    selected = day or today_cn()
    return datetime.combine(selected, time.min)


def day_window_cn(day: date | None = None) -> tuple[datetime, datetime]:
    """Half-open ``[start, end)`` window for one Shanghai calendar day."""
    start = day_start_cn(day)
    return start, start + timedelta(days=1)
