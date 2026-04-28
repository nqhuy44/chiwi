"""Mobile API routes — fast read-only endpoints for the Android app.

All endpoints are authenticated via X-User-Id header (same allow-list as the
notification webhook). No AI is invoked here; every response is a direct
MongoDB read or a pre-computed Redis-cached dashboard payload.
"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException, Query

from src.core.categories import load_categories
from src.core.config import settings
from src.core.dependencies import container
from src.core.schemas import (
    MobileBudgetItem,
    MobileBudgetListResponse,
    MobileCategoryItem,
    MobileCategorySpendingResponse,
    MobileDashboardResponse,
    MobileGoalItem,
    MobileGoalListResponse,
    MobileNudgeItem,
    MobileNudgeListResponse,
    MobileSubscriptionItem,
    MobileSubscriptionListResponse,
    MobileTransactionItem,
    MobileTransactionListResponse,
)
from src.core.utils import get_budget_window, get_date_range
from src.db.repositories.budget_repo import effective_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


def _require_user(x_user_id: str = Header(...)) -> str:
    if x_user_id not in settings.allowed_user_ids:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return x_user_id


def _category_icon_map() -> dict[str, str]:
    return {c.name: c.icon_emoji for c in load_categories()}


def _fmt_txn(doc: dict, icons: dict[str, str]) -> MobileTransactionItem:
    cat = doc.get("category_id") or "Khác"
    ts = doc.get("transaction_time", datetime.now(UTC))
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return MobileTransactionItem(
        id=str(doc.get("_id", "")),
        amount=doc.get("amount", 0),
        direction=doc.get("direction", "outflow"),
        merchant=doc.get("merchant_name"),
        category=cat,
        icon=icons.get(cat, "❓"),
        note="",
        timestamp=ts,
        locked=doc.get("locked", False),
        source=doc.get("source", ""),
    )


@router.get("/dashboard", response_model=MobileDashboardResponse)
async def get_dashboard(x_user_id: str = Header(...)) -> MobileDashboardResponse:
    """Home-screen payload: period totals, top categories, recent transactions,
    budget alerts, and upcoming subscriptions. Cached in Redis for 5 minutes;
    invalidated on every transaction write/delete/correction."""
    _require_user(x_user_id)
    data = await container.dashboard_service.get_or_compute(x_user_id)
    return MobileDashboardResponse(**data)


@router.get("/transactions", response_model=MobileTransactionListResponse)
async def list_transactions(
    x_user_id: str = Header(...),
    period: str = Query("this_month"),
    category: str | None = Query(None),
    direction: str | None = Query(None, pattern="^(inflow|outflow)$"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
) -> MobileTransactionListResponse:
    """Paginated transaction list. ``cursor`` is the ``id`` of the last item
    on the previous page; omit for the first page."""
    _require_user(x_user_id)
    icons = _category_icon_map()

    start_date, end_date = get_date_range(period)
    if start_date is None:
        raise HTTPException(status_code=400, detail=f"Unsupported period: {period}")

    txns = await container.transaction_repo.find_paged(
        user_id=x_user_id,
        start_date=start_date,
        end_date=end_date,
        category_id=category,
        direction=direction,
        limit=limit,
        after_id=cursor,
    )

    total = await container.transaction_repo.count_in_period(
        user_id=x_user_id,
        start_date=start_date,
        end_date=end_date,
        category_id=category,
        direction=direction,
    )

    next_cursor = str(txns[-1]["_id"]) if len(txns) == limit else None

    return MobileTransactionListResponse(
        transactions=[_fmt_txn(t, icons) for t in txns],
        next_cursor=next_cursor,
        total_in_period=total,
    )


@router.get("/budgets", response_model=MobileBudgetListResponse)
async def list_budgets(x_user_id: str = Header(...)) -> MobileBudgetListResponse:
    """Active budgets with current spend vs limit for the ongoing cycle."""
    _require_user(x_user_id)
    icons = _category_icon_map()
    budgets = await container.budget_repo.find_by_user(x_user_id)
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    items: list[MobileBudgetItem] = []

    for b in budgets:
        period = b.get("period", "monthly")
        w_start, w_end = get_budget_window(period)
        if not w_start or not w_end:
            continue

        category_id = b.get("category_id", "")
        limit = effective_limit(b, now_utc)

        txns = await container.transaction_repo.find_by_user(
            user_id=x_user_id, start_date=w_start, end_date=w_end, limit=1000
        )
        spent = sum(
            t.get("amount", 0)
            for t in txns
            if t.get("direction") == "outflow"
            and (t.get("category_id") or "").lower() == category_id.lower()
        )

        remaining = max(0.0, limit - spent)
        pct = int((spent / limit) * 100) if limit > 0 else 0

        if w_start.tzinfo is None:
            w_start = w_start.replace(tzinfo=UTC)
        if w_end.tzinfo is None:
            w_end = w_end.replace(tzinfo=UTC)

        items.append(
            MobileBudgetItem(
                id=str(b.get("_id", "")),
                category=category_id,
                icon=icons.get(category_id, "❓"),
                period=period,
                limit=round(limit),
                spent=round(spent),
                remaining=round(remaining),
                percent_used=pct,
                window_start=w_start,
                window_end=w_end,
                alert_enabled=not b.get("is_silenced", False),
            )
        )

    return MobileBudgetListResponse(budgets=items)


@router.get("/goals", response_model=MobileGoalListResponse)
async def list_goals(x_user_id: str = Header(...)) -> MobileGoalListResponse:
    """Active savings goals with progress."""
    _require_user(x_user_id)
    goals = await container.goal_repo.find_by_user(x_user_id, status="active")
    now_utc = datetime.now(UTC)
    items: list[MobileGoalItem] = []

    for g in goals:
        target = g.get("target_amount", 1) or 1
        saved = g.get("current_amount", 0)
        pct = int((saved / target) * 100)
        deadline = g.get("deadline")

        monthly_needed: float | None = None
        on_track = False
        if deadline:
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            months_left = max(
                1,
                (deadline.year - now_utc.year) * 12
                + (deadline.month - now_utc.month),
            )
            remaining = max(0.0, target - saved)
            monthly_needed = round(remaining / months_left)
            on_track = pct >= int(
                (
                    (now_utc - g.get("created_at", now_utc).replace(tzinfo=UTC if g.get("created_at") and g["created_at"].tzinfo is None else None))
                    .days
                    / max(1, (deadline - g.get("created_at", now_utc).replace(tzinfo=UTC if g.get("created_at") and g["created_at"].tzinfo is None else None)).days)
                )
                * 100
            )

        items.append(
            MobileGoalItem(
                id=str(g.get("_id", "")),
                name=g.get("name", ""),
                target_amount=round(target),
                saved_amount=round(saved),
                percent_achieved=min(100, pct),
                monthly_needed=monthly_needed,
                deadline=deadline,
                on_track=on_track,
            )
        )

    return MobileGoalListResponse(goals=items)


@router.get("/subscriptions", response_model=MobileSubscriptionListResponse)
async def list_subscriptions(
    x_user_id: str = Header(...),
) -> MobileSubscriptionListResponse:
    """Active subscriptions with next charge date and monthly cost summary."""
    _require_user(x_user_id)
    subs = await container.subscription_repo.find_by_user(x_user_id)
    now_utc = datetime.now(UTC)
    items: list[MobileSubscriptionItem] = []
    monthly_total = 0.0

    for s in subs:
        ncd = s.get("next_charge_date")
        if ncd is None:
            continue
        if ncd.tzinfo is None:
            ncd = ncd.replace(tzinfo=UTC)
        due_in = (ncd - now_utc).days
        is_overdue = due_in < 0

        amount = s.get("amount", 0)
        period = s.get("period", "monthly")
        if period == "weekly":
            monthly_total += amount * 4.33
        elif period == "monthly":
            monthly_total += amount
        elif period == "yearly":
            monthly_total += amount / 12

        items.append(
            MobileSubscriptionItem(
                id=str(s.get("_id", "")),
                name=s.get("name", ""),
                amount=amount,
                period=period,
                next_charge_date=ncd,
                due_in_days=due_in,
                is_overdue=is_overdue,
            )
        )

    return MobileSubscriptionListResponse(
        subscriptions=items,
        monthly_total=round(monthly_total),
    )


@router.get("/nudges", response_model=MobileNudgeListResponse)
async def list_nudges(
    x_user_id: str = Header(...),
    limit: int = Query(20, ge=1, le=50),
) -> MobileNudgeListResponse:
    """Recent nudges sent by Mai — last 30 days, newest first."""
    _require_user(x_user_id)
    nudges = await container.nudge_repo.find_recent(
        x_user_id, hours=720, limit=limit
    )
    items: list[MobileNudgeItem] = []
    for n in nudges:
        sent_at = n.get("sent_at", datetime.now(UTC))
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=UTC)
        items.append(
            MobileNudgeItem(
                id=str(n.get("_id", "")),
                type=n.get("nudge_type", ""),
                body=n.get("message", ""),
                sent_at=sent_at,
            )
        )
    return MobileNudgeListResponse(nudges=items)


@router.get("/categories/spending", response_model=MobileCategorySpendingResponse)
async def category_spending(
    x_user_id: str = Header(...),
    period: str = Query("this_month"),
) -> MobileCategorySpendingResponse:
    """Category spending breakdown for a period — used for pie/bar charts."""
    _require_user(x_user_id)
    icons = _category_icon_map()

    start_date, end_date = get_date_range(period)
    if start_date is None:
        raise HTTPException(status_code=400, detail=f"Unsupported period: {period}")

    totals = await container.transaction_repo.aggregate_by_category(
        x_user_id, start_date, end_date
    )

    total_outflow = sum(r["total"] for r in totals) or 1
    breakdown = [
        MobileCategoryItem(
            name=r["category_id"],
            icon=icons.get(r["category_id"], "❓"),
            amount=r["total"],
            tx_count=r["tx_count"],
            percent=round(r["total"] / total_outflow * 100, 1),
        )
        for r in totals
    ]

    return MobileCategorySpendingResponse(
        period=period,
        total_outflow=round(total_outflow if total_outflow != 1 else 0),
        breakdown=breakdown,
    )
