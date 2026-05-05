"""Dashboard computation service.

Assembles the mobile home-screen payload from MongoDB and Redis.
No AI dependencies — pure aggregation over existing data.
Cache key: chiwi:dashboard:{user_id}, TTL 5 min.
Invalidated by any transaction write/delete/correction in the orchestrator.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from src.db.models.transaction import TransactionDocument
from src.db.models.budget import BudgetDocument

from src.core.categories import load_categories
from src.core.profiles import get_profile
from src.core.utils import get_budget_window, get_date_range
from src.db.repositories.budget_repo import effective_limit

logger = logging.getLogger(__name__)

_PERIOD_LABELS = ("today", "this_week", "this_month")


def _category_icon_map() -> dict[str, str]:
    return {c.name: c.icon_emoji for c in load_categories()}


def _period_expense(txns: list[TransactionDocument]) -> float:
    outflow = sum(t.amount for t in txns if t.direction == "outflow")
    return round(outflow)


def _fmt_txn(doc: TransactionDocument, icons: dict[str, str]) -> dict:
    txn_id = str(doc.id)
    cat = doc.category_id or "Khác"
    return {
        "id": txn_id,
        "amount": doc.amount,
        "direction": doc.direction,
        "merchant": doc.merchant_name,
        "category": cat,
        "icon": icons.get(cat, "❓"),
        "note": "",
        "timestamp": doc.transaction_time.isoformat() if doc.transaction_time else datetime.now(UTC).isoformat(),
        "locked": doc.locked,
        "source": doc.source,
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

    async def _sum_outflow(self, user_id: str, start: datetime, end: datetime) -> float:
        """Efficiently sum outflows in a range using MongoDB aggregation."""
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "direction": "outflow",
                    "transaction_time": {"$gte": start, "$lte": end},
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
        ]
        res = await TransactionDocument.aggregate(pipeline).to_list(length=1)
        return round(res[0]["total"]) if res else 0.0

    async def _compute(self, user_id: str) -> dict:
        icons = _category_icon_map()
        profile = await get_profile(user_id)
        tz = profile.timezone

        # 1. Base ranges
        today_start, today_end = get_date_range("today", tz)
        yesterday_start, yesterday_end = get_date_range("yesterday", tz)
        week_start, week_end = get_date_range("this_week", tz)
        last_week_comp_start, last_week_comp_end = get_date_range("last_week_same_period", tz)
        month_start, month_end = get_date_range("this_month", tz)
        last_month_comp_start, last_month_comp_end = get_date_range("last_month_same_period", tz)

        # 2. Extended ranges for New Insights
        # - Avg 7d: last 7 days including today
        avg7d_start = today_start - timedelta(days=6)
        # - Full last week
        last_week_start, last_week_end = get_date_range("last_week", tz)
        # - Avg 4w: last 28 days including today
        avg4w_start = today_start - timedelta(days=27)
        # - Full last month
        last_month_start, last_month_end = get_date_range("last_month", tz)
        # - Avg 3m: approx last 90 days
        avg3m_start = today_start - timedelta(days=89)

        (
            today_txns,
            yesterday_txns,
            week_txns,
            last_week_comp_txns,
            month_txns,
            last_month_comp_txns,
            category_totals,
            recent_txns,
            budgets,
            upcoming_subs,
            just_paid_txns,
            # New insight totals
            total_7d,
            total_last_week,
            total_4w,
            total_last_month,
            total_3m,
        ) = await asyncio.gather(
            self._transaction_repo.find_by_user(user_id, today_start, today_end, limit=200),
            self._transaction_repo.find_by_user(user_id, yesterday_start, yesterday_end, limit=200),
            self._transaction_repo.find_by_user(user_id, week_start, week_end, limit=500),
            self._transaction_repo.find_by_user(user_id, last_week_comp_start, last_week_comp_end, limit=500),
            self._transaction_repo.find_by_user(user_id, month_start, month_end, limit=1000),
            self._transaction_repo.find_by_user(user_id, last_month_comp_start, last_month_comp_end, limit=1000),
            self._transaction_repo.aggregate_by_category(user_id, month_start, month_end),
            self._transaction_repo.find_by_user(user_id, limit=5),
            self._budget_repo.find_by_user(user_id),
            self._subscription_repo.find_upcoming(user_id, within_hours=72),
            self._transaction_repo.find_by_user_with_subscription(
                user_id, start_date=datetime.now(UTC) - timedelta(days=3), limit=10
            ),
            # New insight totals
            self._sum_outflow(user_id, avg7d_start, today_end),
            self._sum_outflow(user_id, last_week_start, last_week_end),
            self._sum_outflow(user_id, avg4w_start, today_end),
            self._sum_outflow(user_id, last_month_start, last_month_end),
            self._sum_outflow(user_id, avg3m_start, today_end),
        )

        top_categories = [
            {
                "name": r["category_id"],
                "icon": icons.get(r["category_id"], "❓"),
                "amount": r["total"],
                "tx_count": r["tx_count"],
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
            ncd = sub.next_charge_date
            if not ncd:
                continue
            if ncd.tzinfo is None:
                ncd = ncd.replace(tzinfo=UTC)
            
            # Filter strictly to 3 days as per user request
            if ncd > now_utc + timedelta(days=3):
                continue

            due_in = max(0, (ncd - now_utc).days)
            upcoming.append({
                "name": sub.name,
                "amount": sub.amount,
                "next_charge_date": ncd.isoformat(),
                "due_in_days": due_in,
            })

        just_paid = []
        for txn in just_paid_txns:
            just_paid.append({
                "name": txn.merchant_name or "Subscription",
                "amount": txn.amount,
                "paid_at": txn.transaction_time.isoformat(),
            })

        return {
            "computed_at": now_utc.isoformat(),
            "is_cached": False,
            "periods": {
                "today": _period_expense(today_txns),
                "yesterday": _period_expense(yesterday_txns),
                "this_week": _period_expense(week_txns),
                "last_week_same_period": _period_expense(last_week_comp_txns),
                "this_month": _period_expense(month_txns),
                "last_month_same_period": _period_expense(last_month_comp_txns),
                # New insights
                "avg_7d": round(total_7d / 7),
                "avg_4w": round(total_4w / 4),
                "avg_3m": round(total_3m / 3),
                "last_week_total": total_last_week,
                "last_month_total": total_last_month,
            },
            "top_categories": top_categories,
            "recent_transactions": [_fmt_txn(t, icons) for t in recent_txns],
            "budget_alerts": budget_alerts,
            "upcoming_subscriptions": upcoming,
            "just_paid_subscriptions": just_paid,
        }


    async def _build_budget_alerts(
        self,
        user_id: str,
        budgets: list[BudgetDocument],
        txns_by_period: dict[str, list[TransactionDocument]],
        icons: dict[str, str],
        tz: str,
    ) -> list[dict]:
        alerts = []
        now_utc = datetime.now(UTC).replace(tzinfo=None)

        for budget in budgets:
            if budget.is_silenced:
                continue
            period = budget.period
            limit = effective_limit(budget, now_utc)
            if limit <= 0:
                continue
            category_id = budget.category_id

            if period in txns_by_period:
                txns = txns_by_period[period]
                spent = sum(
                    t.amount
                    for t in txns
                    if t.direction == "outflow"
                    and (t.category_id or "").lower() == category_id.lower()
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
                    t.amount
                    for t in txns
                    if t.direction == "outflow"
                    and (t.category_id or "").lower() == category_id.lower()
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
