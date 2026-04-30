"""Spending average computation.

Single source of truth for all average calculations in ChiWi.
Used by the worker (spike detection, saving streak) and the
Conversational/Analytics paths (ask_spending_vs_avg).

Averages are always computed from complete past periods so a
partially-elapsed current period never dilutes the baseline.

Zero-spend periods ARE included in the denominator — a day/week
with no outflows is real data (the user didn't spend), not missing data.
However, periods that fall entirely before the user's first recorded
transaction are excluded so new users don't get false baselines.
"""

from __future__ import annotations

import logging
from calendar import monthrange
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, time, timedelta
from typing import Literal
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

Period = Literal["daily", "weekly", "monthly"]
SCOPE_TOTAL = "total"

# How many complete past periods to average over by default
DEFAULT_BASELINE: dict[Period, int] = {
    "daily": 14,
    "weekly": 4,
    "monthly": 3,
}

# Minimum complete periods required before we trust the average
MIN_PERIODS_REQUIRED = 2


@dataclass
class PeriodWindow:
    start: datetime   # UTC inclusive
    end: datetime     # UTC inclusive


@dataclass
class AverageResult:
    scope: str             # "total" or category_id
    period: Period
    average: float         # average outflow per complete past period
    current: float         # outflow in the current (in-progress) period
    periods_used: int      # how many complete periods fed into `average`
    has_baseline: bool     # False when periods_used < MIN_PERIODS_REQUIRED
    pct_diff: float | None # (current/average − 1) × 100; None when no baseline

    @property
    def is_above_avg(self) -> bool | None:
        if self.pct_diff is None:
            return None
        return self.pct_diff > 0

    @property
    def ratio(self) -> float | None:
        if not self.has_baseline or self.average == 0:
            return None
        return round(self.current / self.average, 2)


def _tz(timezone: str) -> ZoneInfo:
    return ZoneInfo(timezone)


def _day_bounds_utc(d: date, tz: ZoneInfo) -> tuple[datetime, datetime]:
    start = datetime.combine(d, time.min, tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
    end = datetime.combine(d, time.max, tzinfo=tz).astimezone(UTC).replace(tzinfo=None)
    return start, end


def _past_complete_periods(
    period: Period,
    n: int,
    timezone: str,
) -> list[PeriodWindow]:
    """Return the last `n` complete calendar periods before the current one."""
    tz = _tz(timezone)
    today = datetime.now(tz).date()
    windows: list[PeriodWindow] = []

    if period == "daily":
        for i in range(1, n + 1):
            d = today - timedelta(days=i)
            s, e = _day_bounds_utc(d, tz)
            windows.append(PeriodWindow(s, e))

    elif period == "weekly":
        # Current week starts on Monday
        current_week_monday = today - timedelta(days=today.weekday())
        for i in range(1, n + 1):
            week_start = current_week_monday - timedelta(weeks=i)
            week_end = week_start + timedelta(days=6)
            s, _ = _day_bounds_utc(week_start, tz)
            _, e = _day_bounds_utc(week_end, tz)
            windows.append(PeriodWindow(s, e))

    elif period == "monthly":
        year, month = today.year, today.month
        for _ in range(n):
            month -= 1
            if month == 0:
                month = 12
                year -= 1
            _, last_day = monthrange(year, month)
            first = date(year, month, 1)
            last = date(year, month, last_day)
            s, _ = _day_bounds_utc(first, tz)
            _, e = _day_bounds_utc(last, tz)
            windows.append(PeriodWindow(s, e))

    return windows


def _current_period_window(period: Period, timezone: str) -> PeriodWindow:
    """Return the start of the current period to now (UTC)."""
    tz = _tz(timezone)
    now_local = datetime.now(tz)
    today = now_local.date()
    now_utc = now_local.astimezone(UTC).replace(tzinfo=None)

    if period == "daily":
        start, _ = _day_bounds_utc(today, tz)
        return PeriodWindow(start, now_utc)

    if period == "weekly":
        monday = today - timedelta(days=today.weekday())
        start, _ = _day_bounds_utc(monday, tz)
        return PeriodWindow(start, now_utc)

    # monthly
    first = today.replace(day=1)
    start, _ = _day_bounds_utc(first, tz)
    return PeriodWindow(start, now_utc)


def _sum_outflows(txns: list[dict], scope: str) -> float:
    total = 0.0
    for t in txns:
        if t.get("direction") != "outflow":
            continue
        if scope != SCOPE_TOTAL:
            cat = (t.get("category_id") or "").strip().lower()
            if cat != scope.strip().lower():
                continue
        total += t.get("amount", 0)
    return total


async def compute_avg(
    transaction_repo,
    user_id: str,
    period: Period,
    scope: str = SCOPE_TOTAL,
    baseline_n: int | None = None,
    timezone: str = "Asia/Ho_Chi_Minh",
) -> AverageResult:
    """Compute the average and current-period spending for one (period, scope) combination.

    Args:
        transaction_repo: TransactionRepository instance.
        user_id: The user to compute for.
        period: "daily", "weekly", or "monthly".
        scope: "total" for all categories, or a category_id string.
        baseline_n: Number of complete past periods to average. Defaults
            to DEFAULT_BASELINE[period].
        timezone: IANA timezone string for day-boundary math.

    Returns:
        AverageResult with average, current, pct_diff, and has_baseline.
    """
    n = baseline_n if baseline_n is not None else DEFAULT_BASELINE[period]
    past_windows = _past_complete_periods(period, n, timezone)
    current_window = _current_period_window(period, timezone)

    # Fetch all transactions covering the baseline + current window in one query
    if not past_windows:
        oldest_start = current_window.start
    else:
        oldest_start = past_windows[-1].start  # oldest window is last in list

    all_txns = [
        t.model_dump()
        for t in await transaction_repo.find_by_user(
            user_id=user_id,
            start_date=oldest_start,
            end_date=current_window.end,
            limit=1000,
        )
    ]

    if not all_txns:
        return AverageResult(
            scope=scope, period=period,
            average=0, current=0,
            periods_used=0, has_baseline=False, pct_diff=None,
        )

    # Find first transaction time to exclude pre-history periods
    first_txn_time = min(
        t.get("transaction_time") or t.get("created_at") or current_window.start
        for t in all_txns
    )
    first_txn_time = (
        first_txn_time.replace(tzinfo=None) if first_txn_time.tzinfo else first_txn_time
    )

    # Sum each past complete period
    period_totals: list[float] = []
    for w in past_windows:
        # Skip periods entirely before first transaction
        if w.end < first_txn_time:
            continue
        period_txns = [
            t for t in all_txns
            if _in_window(t, w)
        ]
        period_totals.append(_sum_outflows(period_txns, scope))

    periods_used = len(period_totals)
    average = sum(period_totals) / periods_used if periods_used > 0 else 0.0
    has_baseline = periods_used >= MIN_PERIODS_REQUIRED

    # Current period
    current_txns = [t for t in all_txns if _in_window(t, current_window)]
    current = _sum_outflows(current_txns, scope)

    pct_diff: float | None = None
    if has_baseline and average > 0:
        pct_diff = round((current / average - 1) * 100, 1)
    elif has_baseline and average == 0 and current > 0:
        pct_diff = None  # can't compute ratio from zero baseline

    logger.debug(
        "avg(%s, %s, %s): avg=%.0f current=%.0f periods=%d",
        user_id, period, scope, average, current, periods_used,
    )
    return AverageResult(
        scope=scope, period=period,
        average=round(average),
        current=round(current),
        periods_used=periods_used,
        has_baseline=has_baseline,
        pct_diff=pct_diff,
    )


def _in_window(txn: dict, w: PeriodWindow) -> bool:
    ts = txn.get("transaction_time") or txn.get("created_at")
    if not ts:
        return False
    ts = ts.replace(tzinfo=None) if ts.tzinfo else ts
    return w.start <= ts <= w.end


async def compute_avg_all_categories(
    transaction_repo,
    user_id: str,
    period: Period,
    baseline_n: int | None = None,
    timezone: str = "Asia/Ho_Chi_Minh",
) -> tuple[AverageResult, list[AverageResult]]:
    """Compute total average plus per-category averages in one pass.

    Returns:
        (total_result, [category_result, ...]) sorted by current spend descending.
    """
    n = baseline_n if baseline_n is not None else DEFAULT_BASELINE[period]
    past_windows = _past_complete_periods(period, n, timezone)
    current_window = _current_period_window(period, timezone)

    if not past_windows:
        oldest_start = current_window.start
    else:
        oldest_start = past_windows[-1].start

    all_txns = [
        t.model_dump()
        for t in await transaction_repo.find_by_user(
            user_id=user_id,
            start_date=oldest_start,
            end_date=current_window.end,
            limit=1000,
        )
    ]

    if not all_txns:
        empty = AverageResult(
            scope=SCOPE_TOTAL, period=period,
            average=0, current=0, periods_used=0,
            has_baseline=False, pct_diff=None,
        )
        return empty, []

    first_txn_time = min(
        (t.get("transaction_time") or t.get("created_at") or current_window.start)
        for t in all_txns
    )
    first_txn_time = (
        first_txn_time.replace(tzinfo=None) if first_txn_time.tzinfo else first_txn_time
    )

    # Collect active category ids from the transaction set
    categories: set[str] = set()
    for t in all_txns:
        if t.get("direction") == "outflow" and t.get("category_id"):
            categories.add(t["category_id"].strip())

    def _build_result(scope: str) -> AverageResult:
        totals: list[float] = []
        for w in past_windows:
            if w.end < first_txn_time:
                continue
            pw_txns = [t for t in all_txns if _in_window(t, w)]
            totals.append(_sum_outflows(pw_txns, scope))

        pu = len(totals)
        avg = sum(totals) / pu if pu > 0 else 0.0
        hb = pu >= MIN_PERIODS_REQUIRED

        cur_txns = [t for t in all_txns if _in_window(t, current_window)]
        cur = _sum_outflows(cur_txns, scope)

        pct: float | None = None
        if hb and avg > 0:
            pct = round((cur / avg - 1) * 100, 1)

        return AverageResult(
            scope=scope, period=period,
            average=round(avg), current=round(cur),
            periods_used=pu, has_baseline=hb, pct_diff=pct,
        )

    total_result = _build_result(SCOPE_TOTAL)
    cat_results = sorted(
        (_build_result(cat) for cat in categories),
        key=lambda r: r.current,
        reverse=True,
    )

    return total_result, cat_results
