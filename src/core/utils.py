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


def _resolve_tz(timezone: str | None) -> ZoneInfo:
    return ZoneInfo(timezone or settings.business_timezone)


def _local_day_bounds(d: date, tz: ZoneInfo) -> Tuple[datetime, datetime]:
    """Return (00:00, 23:59:59.999999) for a local calendar day, in UTC."""
    start_local = datetime.combine(d, time.min, tzinfo=tz)
    end_local = datetime.combine(d, time.max, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


def get_date_range(
    period: str, timezone: str | None = None
) -> Tuple[datetime, datetime]:
    """Calculate (start_utc, end_utc) for a period label.

    ``timezone`` overrides ``settings.business_timezone`` so per-user
    day boundaries are correct regardless of server location.
    Returns (None, None) for unrecognized periods.
    """
    tz = _resolve_tz(timezone)
    now_local = datetime.now(tz)
    today = now_local.date()

    if period == "today":
        return _local_day_bounds(today, tz)

    if period == "this_week":
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
        start, _ = _local_day_bounds(start_of_last_week, tz)
        _, end = _local_day_bounds(end_of_last_week, tz)
        return start, end

    if period == "last_week_same_period":
        # Start of last week (Monday)
        monday_this_week = today - timedelta(days=today.weekday())
        monday_last_week = monday_this_week - timedelta(days=7)
        # End day is "today - 7 days"
        same_day_last_week = today - timedelta(days=7)
        
        start, _ = _local_day_bounds(monday_last_week, tz)
        _, end = _local_day_bounds(same_day_last_week, tz)
        return start, end

    if period == "last_month":
        first_of_this_month = today.replace(day=1)
        end_of_last_month = first_of_this_month - timedelta(days=1)
        start_of_last_month = end_of_last_month.replace(day=1)
        start, _ = _local_day_bounds(start_of_last_month, tz)
        _, end = _local_day_bounds(end_of_last_month, tz)
        return start, end

    if period == "yesterday":
        yesterday = today - timedelta(days=1)
        return _local_day_bounds(yesterday, tz)

    if period == "last_month_same_period":
        # First day of this month
        first_of_this_month = today.replace(day=1)
        # Last month boundaries
        last_month_ref = first_of_this_month - timedelta(days=1)
        start_of_last_month = last_month_ref.replace(day=1)

        # Determine the "same day" in last month
        _, last_month_max_days = monthrange(start_of_last_month.year, start_of_last_month.month)
        same_day_last_month = min(today.day, last_month_max_days)

        end_date_last_month = start_of_last_month.replace(day=same_day_last_month)

        start, _ = _local_day_bounds(start_of_last_month, tz)
        _, end = _local_day_bounds(end_date_last_month, tz)
        return start, end

    return None, None


def parse_custom_range(
    start_iso: str | None,
    end_iso: str | None,
    timezone: str | None = None,
) -> Tuple[datetime | None, datetime | None]:
    """Parse ISO8601 start/end strings into a UTC datetime pair.

    Strings without tzinfo are interpreted in the user/business timezone.
    Returns (None, None) on any parse failure.
    """
    tz = _resolve_tz(timezone)

    def _parse(s: str | None, is_end: bool = False) -> datetime | None:
        if not s:
            return None
        try:
            # Handle plain dates like "2026-05-01"
            if len(s) == 10:
                d = date.fromisoformat(s)
                dt = datetime.combine(d, time.max if is_end else time.min, tzinfo=tz)
            else:
                dt = datetime.fromisoformat(s)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=tz)
            return dt.astimezone(UTC).replace(tzinfo=None)
        except (ValueError, TypeError):
            return None

    return _parse(start_iso), _parse(end_iso, is_end=True)


def resolve_date_range(
    period: str,
    start_iso: str | None = None,
    end_iso: str | None = None,
    timezone: str | None = None,
) -> Tuple[datetime | None, datetime | None]:
    """Resolve any period label or custom ISO range to (start_utc, end_utc).

    Prioritizes start_iso/end_iso if provided.
    """
    if start_iso or end_iso:
        return parse_custom_range(start_iso, end_iso, timezone)
    return get_date_range(period, timezone)


def get_budget_window(
    budget_period: str, timezone: str | None = None
) -> Tuple[datetime | None, datetime | None]:
    """Return (start, end) for a budget cycle containing today.

    Unlike get_date_range("this_week"/"this_month") which end at `now`,
    budgets span the full local cycle.
    """
    tz = _resolve_tz(timezone)
    today = datetime.now(tz).date()

    if budget_period == "weekly":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        start, _ = _local_day_bounds(monday, tz)
        _, end = _local_day_bounds(sunday, tz)
        return start, end

    if budget_period == "monthly":
        _, last_day = monthrange(today.year, today.month)
        start, _ = _local_day_bounds(today.replace(day=1), tz)
        _, end = _local_day_bounds(today.replace(day=last_day), tz)
        return start, end

    return None, None


def get_comparison_ranges(
    period: str,
    compare_period: str | None = None,
    timezone: str | None = None,
) -> Tuple[Tuple[datetime, datetime], Tuple[datetime, datetime]]:
    """Return (current_range, comparison_range) for period-over-period analysis.

    If compare_period is not provided, automatically infer the comparison:
      - this_week  -> last_week
      - this_month -> last_month_same_period
      - today      -> yesterday
    """
    current = get_date_range(period, timezone)

    if compare_period:
        comparison = get_date_range(compare_period, timezone)
    else:
        mapping = {
            "this_week": "last_week_same_period",
            "this_month": "last_month_same_period",
            "today": "yesterday",
        }
        inferred = mapping.get(period, "last_week")
        comparison = get_date_range(inferred, timezone)

    return current, comparison
