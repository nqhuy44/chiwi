"""Date range utilities for reporting and analytics."""

from calendar import monthrange
from datetime import UTC, datetime, time, timedelta
from typing import Tuple


def get_date_range(period: str) -> Tuple[datetime, datetime]:
    """Calculate start and end datetime for a given period string."""
    now = datetime.now(UTC)
    today = now.date()

    if period == "today":
        start = datetime.combine(today, time.min, tzinfo=UTC)
        end = datetime.combine(today, time.max, tzinfo=UTC)
    elif period == "this_week":
        # Start of week (Monday)
        start_of_week = today - timedelta(days=today.weekday())
        start = datetime.combine(start_of_week, time.min, tzinfo=UTC)
        end = now
    elif period == "this_month":
        # Start of month
        start_of_month = today.replace(day=1)
        start = datetime.combine(start_of_month, time.min, tzinfo=UTC)
        end = now
    elif period == "last_week":
        # Previous full week (Monday to Sunday)
        end_of_last_week = today - timedelta(days=today.weekday() + 1)
        start_of_last_week = end_of_last_week - timedelta(days=6)
        start = datetime.combine(start_of_last_week, time.min, tzinfo=UTC)
        end = datetime.combine(end_of_last_week, time.max, tzinfo=UTC)
    elif period == "last_month":
        # Previous full month
        first_of_this_month = today.replace(day=1)
        end_of_last_month = first_of_this_month - timedelta(days=1)
        start_of_last_month = end_of_last_month.replace(day=1)
        start = datetime.combine(start_of_last_month, time.min, tzinfo=UTC)
        end = datetime.combine(end_of_last_month, time.max, tzinfo=UTC)
    else:
        # Return None for unrecognized periods to handle in orchestrator
        return None, None

    return start, end


def get_budget_window(
    budget_period: str,
) -> Tuple[datetime | None, datetime | None]:
    """Return (start, end) for a budget cycle containing today.

    Unlike get_date_range("this_week"/"this_month") which end at `now`,
    budgets span the full period (Mon-Sun week or 1st-last of month).
    """
    today = datetime.now(UTC).date()

    if budget_period == "weekly":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return (
            datetime.combine(monday, time.min, tzinfo=UTC),
            datetime.combine(sunday, time.max, tzinfo=UTC),
        )

    if budget_period == "monthly":
        _, last_day = monthrange(today.year, today.month)
        return (
            datetime.combine(today.replace(day=1), time.min, tzinfo=UTC),
            datetime.combine(today.replace(day=last_day), time.max, tzinfo=UTC),
        )

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
    current_start, current_end = get_date_range(period)

    if compare_period:
        comp_start, comp_end = get_date_range(compare_period)
    else:
        # Auto-infer comparison period
        mapping = {
            "this_week": "last_week",
            "this_month": "last_month",
            "today": "yesterday",
        }
        inferred = mapping.get(period, "last_week")

        if inferred == "yesterday":
            yesterday = datetime.now(UTC).date() - timedelta(days=1)
            comp_start = datetime.combine(yesterday, time.min, tzinfo=UTC)
            comp_end = datetime.combine(yesterday, time.max, tzinfo=UTC)
        else:
            comp_start, comp_end = get_date_range(inferred)

    return (current_start, current_end), (comp_start, comp_end)
