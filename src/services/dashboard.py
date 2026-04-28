"""Dashboard computation service.

Assembles the mobile home-screen payload from MongoDB and Redis.
No AI dependencies — pure aggregation over existing data.
Cache key: chiwi:dashboard:{user_id}, TTL 5 min.
Invalidated by any transaction write/delete/correction in the orchestrator.
"""

import asyncio
import logging
from datetime import UTC, datetime

from src.core.categories import load_categories
from src.core.profiles import get_profile
from src.core.utils import get_budget_window, get_date_range
from src.db.repositories.budget_repo import effective_limit

logger = logging.getLogger(__name__)

_PERIOD_LABELS = ("today", "this_week", "this_month")


def _category_icon_map() -> dict[str, str]:
    return {c.name: c.icon_emoji for c in load_categories()}


def _period_stats(txns: list[dict]) -> dict:
    inflow = sum(t.get("amount", 0) for t in txns if t.get("direction") == "inflow")
    outflow = sum(t.get("amount", 0) for t in txns if t.get("direction") == "outflow")
    return {
        "inflow": round(inflow),
        "outflow": round(outflow),
        "net": round(inflow - outflow),
        "tx_count": len(txns),
    }


def _fmt_txn(doc: dict, icons: dict[str, str]) -> dict:
    txn_id = str(doc.get("_id", ""))
    cat = doc.get("category_id") or "Khác"
    return {
        "id": txn_id,
        "amount": doc.get("amount", 0),
        "direction": doc.get("direction", "outflow"),
        "merchant": doc.get("merchant_name"),
        "category": cat,
        "icon": icons.get(cat, "❓"),
        "note": "",
        "timestamp": doc.get("transaction_time", datetime.now(UTC)).isoformat(),
        "locked": doc.get("locked", False),
        "source": doc.get("source", ""),
    }


class DashboardService:
    def __init__(
        self,
        transaction_repo,
        budget_repo,
        goal_repo,
        subscription_repo,
        nudge_repo,
        redis,
    ) -> None:
        self._transaction_repo = transaction_repo
        self._budget_repo = budget_repo
        self._goal_repo = goal_repo
        self._subscription_repo = subscription_repo
        self._nudge_repo = nudge_repo
        self._redis = redis

    async def get_or_compute(self, user_id: str) -> dict:
        cached = await self._redis.get_dashboard_cache(user_id)
        if cached:
            cached["is_cached"] = True
            return cached
        data = await self._compute(user_id)
        await self._redis.set_dashboard_cache(user_id, data)
        return data

    async def invalidate(self, user_id: str) -> None:
        await self._redis.invalidate_dashboard_cache(user_id)

    async def _compute(self, user_id: str) -> dict:
        icons = _category_icon_map()
        profile = get_profile(user_id)
        tz = profile.timezone

        today_start, today_end = get_date_range("today", tz)
        week_start, week_end = get_date_range("this_week", tz)
        month_start, month_end = get_date_range("this_month", tz)

        (
            today_txns,
            week_txns,
            month_txns,
            category_totals,
            recent_txns,
            budgets,
            upcoming_subs,
        ) = await asyncio.gather(
            self._transaction_repo.find_by_user(user_id, today_start, today_end, limit=200),
            self._transaction_repo.find_by_user(user_id, week_start, week_end, limit=500),
            self._transaction_repo.find_by_user(user_id, month_start, month_end, limit=1000),
            self._transaction_repo.aggregate_by_category(user_id, month_start, month_end),
            self._transaction_repo.find_by_user(user_id, limit=5),
            self._budget_repo.find_by_user(user_id),
            self._subscription_repo.find_upcoming(user_id, within_hours=168),
        )

        total_month_outflow = sum(
            r["total"] for r in category_totals if r["total"] > 0
        ) or 1  # avoid division by zero

        top_categories = [
            {
                "name": r["category_id"],
                "icon": icons.get(r["category_id"], "❓"),
                "amount": r["total"],
                "tx_count": r["tx_count"],
                "percent": round(r["total"] / total_month_outflow * 100, 1),
            }
            for r in category_totals[:5]
        ]

        # Budget alerts: use pre-fetched txn lists keyed by budget period
        txns_by_period = {
            "monthly": month_txns,
            "weekly": week_txns,
            "today": today_txns,
        }
        budget_alerts = await self._build_budget_alerts(
            user_id, budgets, txns_by_period, icons, tz
        )

        now_utc = datetime.now(UTC)
        upcoming = []
        for sub in upcoming_subs:
            ncd = sub.get("next_charge_date")
            if not ncd:
                continue
            if ncd.tzinfo is None:
                ncd = ncd.replace(tzinfo=UTC)
            due_in = max(0, (ncd - now_utc).days)
            upcoming.append({
                "name": sub.get("name", ""),
                "amount": sub.get("amount", 0),
                "due_in_days": due_in,
            })

        return {
            "computed_at": now_utc.isoformat(),
            "is_cached": False,
            "periods": {
                "today": _period_stats(today_txns),
                "this_week": _period_stats(week_txns),
                "this_month": _period_stats(month_txns),
            },
            "top_categories": top_categories,
            "recent_transactions": [_fmt_txn(t, icons) for t in recent_txns],
            "budget_alerts": budget_alerts,
            "upcoming_subscriptions": upcoming,
        }

    async def _build_budget_alerts(
        self,
        user_id: str,
        budgets: list[dict],
        txns_by_period: dict[str, list[dict]],
        icons: dict[str, str],
        tz: str,
    ) -> list[dict]:
        alerts = []
        now_utc = datetime.now(UTC).replace(tzinfo=None)

        for budget in budgets:
            if budget.get("is_silenced"):
                continue
            period = budget.get("period", "monthly")
            limit = effective_limit(budget, now_utc)
            if limit <= 0:
                continue
            category_id = budget.get("category_id", "")

            if period in txns_by_period:
                txns = txns_by_period[period]
                spent = sum(
                    t.get("amount", 0)
                    for t in txns
                    if t.get("direction") == "outflow"
                    and (t.get("category_id") or "").lower() == category_id.lower()
                )
            else:
                # yearly or unrecognized: query directly
                b_start, _ = get_budget_window(period, timezone=tz)
                if not b_start:
                    continue
                txns = await self._transaction_repo.find_by_user(
                    user_id, b_start, None, limit=2000
                )
                spent = sum(
                    t.get("amount", 0)
                    for t in txns
                    if t.get("direction") == "outflow"
                    and (t.get("category_id") or "").lower() == category_id.lower()
                )

            pct = int((spent / limit) * 100)
            if pct >= 80:
                alerts.append({
                    "category": category_id,
                    "icon": icons.get(category_id, "❓"),
                    "spent": round(spent),
                    "limit": round(limit),
                    "percent_used": pct,
                })

        return alerts
