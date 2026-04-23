"""Date range utilities for reporting, budgets, and analytics.

All day-boundary math happens in the business timezone (Asia/Ho_Chi_Minh
by default, configurable via settings.business_timezone). The returned
datetimes are converted to UTC so they plug straight into Mongo queries
where transaction_time is stored as UTC.
"""

from calendar import monthrange
from datetime import UTC, date, datetime, time, timedelta
from typing import Tuple
from zoneinfo import ZoneInfo

from src.core.config import settings


def _business_tz() -> ZoneInfo:
    return ZoneInfo(settings.business_timezone)


def _local_day_bounds(d: date) -> Tuple[datetime, datetime]:
    """Return (00:00, 23:59:59.999999) for a local calendar day, in UTC."""
    tz = _business_tz()
    start_local = datetime.combine(d, time.min, tzinfo=tz)
    end_local = datetime.combine(d, time.max, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def get_date_range(period: str) -> Tuple[datetime, datetime]:
    """Calculate (start_utc, end_utc) for a period label.

    Returns (None, None) for unrecognized periods so callers can show a
    friendly error instead of guessing.
    """
    tz = _business_tz()
    now_local = datetime.now(tz)
    today = now_local.date()

    if period == "today":
        return _local_day_bounds(today)

    if period == "this_week":
        # Monday 00:00 local → now
        monday = today - timedelta(days=today.weekday())
        start_local = datetime.combine(monday, time.min, tzinfo=tz)
        return start_local.astimezone(UTC), now_local.astimezone(UTC)

    if period == "this_month":
        first = today.replace(day=1)
        start_local = datetime.combine(first, time.min, tzinfo=tz)
        return start_local.astimezone(UTC), now_local.astimezone(UTC)

    if period == "last_week":
        end_of_last_week = today - timedelta(days=today.weekday() + 1)
        start_of_last_week = end_of_last_week - timedelta(days=6)
        start, _ = _local_day_bounds(start_of_last_week)
        _, end = _local_day_bounds(end_of_last_week)
        return start, end

    if period == "last_month":
        first_of_this_month = today.replace(day=1)
        end_of_last_month = first_of_this_month - timedelta(days=1)
        start_of_last_month = end_of_last_month.replace(day=1)
        start, _ = _local_day_bounds(start_of_last_month)
        _, end = _local_day_bounds(end_of_last_month)
        return start, end

    return None, None


def get_budget_window(
    budget_period: str,
) -> Tuple[datetime | None, datetime | None]:
    """Return (start, end) for a budget cycle containing today.

    Unlike get_date_range("this_week"/"this_month") which end at `now`,
    budgets span the full local cycle.
    """
    tz = _business_tz()
    today = datetime.now(tz).date()

    if budget_period == "weekly":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        start, _ = _local_day_bounds(monday)
        _, end = _local_day_bounds(sunday)
        return start, end

    if budget_period == "monthly":
        _, last_day = monthrange(today.year, today.month)
        start, _ = _local_day_bounds(today.replace(day=1))
        _, end = _local_day_bounds(today.replace(day=last_day))
        return start, end

    return None, None


def get_comparison_ranges(
    period: str, compare_period: str | None = None
) -> Tuple[Tuple[datetime, datetime], Tuple[datetime, datetime]]:
    """Return (current_range, comparison_range) for period-over-period analysis.

    If compare_period is not provided, automatically infer the comparison:
      - this_week  -> last_week
      - this_month -> last_month
      - today      -> yesterday
    """
    current = get_date_range(period)

    if compare_period:
        comparison = get_date_range(compare_period)
    else:
        mapping = {
            "this_week": "last_week",
            "this_month": "last_month",
            "today": "yesterday",
        }
        inferred = mapping.get(period, "last_week")

        if inferred == "yesterday":
            tz = _business_tz()
            yesterday = datetime.now(tz).date() - timedelta(days=1)
            comparison = _local_day_bounds(yesterday)
        else:
            comparison = get_date_range(inferred)

    return current, comparison
