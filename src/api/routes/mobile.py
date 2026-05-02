"""Mobile API routes — fast read-only endpoints for the Android app.

All endpoints require a valid JWT for an active user account. No AI is invoked
on read endpoints; every read response is a direct MongoDB read or a
pre-computed Redis-cached dashboard payload.

The ``POST /chat`` endpoint is the only write-capable endpoint here — it
mirrors the Telegram conversational flow, accepting free-form text and
returning structured JSON instead of sending a Telegram message.
"""

import io
import csv
import logging
from datetime import UTC, datetime
from typing import Literal
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from src.api.dependencies.auth import get_current_user
from src.db.models.transaction import TransactionDocument

from src.core.categories import load_categories
from src.core.config import settings
from src.core.dependencies import container
from src.core.profiles import get_profile
from src.core.schemas import (
    MobileBudgetItem,
    MobileBudgetListResponse,
    MobileCategoryItem,
    MobileCategorySpendingResponse,
    MobileChatAction,
    MobileChatRequest,
    MobileChatResponse,
    MobileDashboardResponse,
    MobileGoalItem,
    MobileGoalListResponse,
    MobileNudgeItem,
    MobileNudgeListResponse,
    MobileSubscriptionItem,
    MobileSubscriptionListResponse,
    MobileTransactionItem,
    MobileTransactionListResponse,
    MobileUnreadCountResponse,
    UserProfile,
)
from src.core.utils import get_budget_window, get_date_range, resolve_date_range, get_sliding_window
from src.db.repositories.budget_repo import effective_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mobile", tags=["mobile"])


# _require_user is deprecated in favor of get_current_user dependency


def _category_icon_map() -> dict[str, str]:
    return {c.name: c.icon_emoji for c in load_categories()}


def _fmt_txn(doc: TransactionDocument, icons: dict[str, str]) -> MobileTransactionItem:
    cat = doc.category_id or "Khác"
    ts = doc.transaction_time or datetime.now(UTC)
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return MobileTransactionItem(
        id=str(doc.id),
        amount=doc.amount,
        direction=doc.direction,
        merchant=doc.merchant_name,
        category=cat,
        icon=icons.get(cat, "❓"),
        note="",
        timestamp=ts,
        locked=doc.locked,
        source=doc.source,
    )


@router.get("/dashboard", response_model=MobileDashboardResponse)
async def get_dashboard(user_id: str = Depends(get_current_user)) -> MobileDashboardResponse:
    """Home-screen payload: period totals, top categories, recent transactions,
    budget alerts, and upcoming subscriptions. Cached in Redis for 5 minutes;
    invalidated on every transaction write/delete/correction."""
    # Authenticated via JWT
    data = await container.dashboard_service.get_or_compute(user_id)
    return MobileDashboardResponse(**data)


@router.get("/transactions", response_model=MobileTransactionListResponse)
async def list_transactions(
    user_id: str = Depends(get_current_user),
    period: str | None = Query(None),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
    category: str | None = Query(None),
    direction: str | None = Query(None, pattern="^(inflow|outflow)$"),
    limit: int = Query(20, ge=1, le=100),
    cursor: str | None = Query(None),
    offset_days: int = Query(0, ge=0),
    window_size: int = Query(7, ge=1),
) -> MobileTransactionListResponse:
    """Paginated transaction list. Supports both period labels, custom
    ISO8601 date ranges, or sliding time windows (offset_days/window_size)."""
    # Authenticated via JWT
    icons = _category_icon_map()

    profile = await get_profile(user_id)
    tz = profile.timezone

    # 1. Resolve Filter Range (The absolute boundaries)
    # Default to "this_month" if absolutely nothing is provided, 
    # but handle it gracefully so it can be intersected.
    f_start, f_end = resolve_date_range(period, start_date, end_date, tz)

    # 2. Resolve Sliding Window Range (The "viewing" block)
    w_start, w_end = get_sliding_window(offset_days, window_size, tz)

    # 3. Intersect Filter and Window
    # start_dt = Max(Filter_Start, Window_Start)
    # end_dt = Min(Filter_End, Window_End)
    start_dt = max(f_start, w_start) if f_start else w_start
    end_dt = min(f_end, w_end) if f_end else w_end

    # Handle the case where the window moves entirely outside the filter
    if f_start and w_end < f_start:
        # Window is older than the filter start
        return MobileTransactionListResponse(
            transactions=[],
            next_cursor=None,
            next_offset_days=None,
            total_in_period=0
        )

    if start_dt is None:
        raise HTTPException(status_code=400, detail=f"Invalid date range or unsupported period")

    txns = await container.transaction_repo.find_paged(
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
        category_id=category,
        direction=direction,
        limit=limit,
        after_id=cursor,
    )

    total = await container.transaction_repo.count_in_period(
        user_id=user_id,
        start_date=start_dt,
        end_date=end_dt,
        category_id=category,
        direction=direction,
    )

    # Pagination logic
    next_cursor: str | None = None
    next_offset_days: int | None = offset_days

    if len(txns) == limit:
        # We might have more in the same window
        next_cursor = str(txns[-1].id)
    else:
        # Window exhausted, suggest next window
        next_cursor = None
        next_offset_days = offset_days + window_size

    return MobileTransactionListResponse(
        transactions=[_fmt_txn(t, icons) for t in txns],
        next_cursor=next_cursor,
        next_offset_days=next_offset_days,
        total_in_period=total,
    )


@router.get("/budgets", response_model=MobileBudgetListResponse)
async def list_budgets(user_id: str = Depends(get_current_user)) -> MobileBudgetListResponse:
    """Active budgets with current spend vs limit for the ongoing cycle."""
    # Authenticated via JWT
    icons = _category_icon_map()
    budgets = await container.budget_repo.find_by_user(user_id)
    now_utc = datetime.now(UTC).replace(tzinfo=None)
    items: list[MobileBudgetItem] = []

    for b in budgets:
        period = b.period
        w_start, w_end = get_budget_window(period)
        if not w_start or not w_end:
            continue

        category_id = b.category_id
        limit = effective_limit(b, now_utc)

        txns = await container.transaction_repo.find_by_user(
            user_id=user_id, start_date=w_start, end_date=w_end, limit=1000
        )
        spent = sum(
            t.amount
            for t in txns
            if t.direction == "outflow"
            and (t.category_id or "").lower() == category_id.lower()
        )

        remaining = max(0.0, limit - spent)
        pct = int((spent / limit) * 100) if limit > 0 else 0

        if w_start.tzinfo is None:
            w_start = w_start.replace(tzinfo=UTC)
        if w_end.tzinfo is None:
            w_end = w_end.replace(tzinfo=UTC)

        items.append(
            MobileBudgetItem(
                id=str(b.id),
                category=category_id,
                icon=icons.get(category_id, "❓"),
                period=period,
                limit=round(limit),
                spent=round(spent),
                remaining=round(remaining),
                percent_used=pct,
                window_start=w_start,
                window_end=w_end,
                alert_enabled=not b.is_silenced,
            )
        )

    return MobileBudgetListResponse(budgets=items)


@router.get("/goals", response_model=MobileGoalListResponse)
async def list_goals(user_id: str = Depends(get_current_user)) -> MobileGoalListResponse:
    """Active savings goals with progress."""
    # Authenticated via JWT
    goals = await container.goal_repo.find_by_user(user_id, status="active")
    now_utc = datetime.now(UTC)
    items: list[MobileGoalItem] = []

    for g in goals:
        target = g.target_amount or 1
        saved = g.current_amount
        pct = int((saved / target) * 100)
        deadline = g.deadline

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
            
            created_at = g.created_at
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=UTC)
                
            on_track = pct >= int(
                (
                    (now_utc - created_at).days
                    / max(1, (deadline - created_at).days)
                )
                * 100
            )

        items.append(
            MobileGoalItem(
                id=str(g.id),
                name=g.name,
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
    user_id: str = Depends(get_current_user),
) -> MobileSubscriptionListResponse:
    """Active subscriptions with next charge date and monthly cost summary."""
    # Authenticated via JWT
    subs = await container.subscription_repo.find_by_user(user_id)
    now_utc = datetime.now(UTC)
    items: list[MobileSubscriptionItem] = []
    monthly_total = 0.0

    for s in subs:
        ncd = s.next_charge_date
        if ncd is None:
            continue
        if ncd.tzinfo is None:
            ncd = ncd.replace(tzinfo=UTC)
        due_in = (ncd - now_utc).days
        is_overdue = due_in < 0

        amount = s.amount
        period = s.period
        if period == "weekly":
            monthly_total += amount * 4.33
        elif period == "monthly":
            monthly_total += amount
        elif period == "yearly":
            monthly_total += amount / 12

        last_charged = s.last_charged_at
        if last_charged and last_charged.tzinfo is None:
            last_charged = last_charged.replace(tzinfo=UTC)

        items.append(
            MobileSubscriptionItem(
                id=str(s.id),
                name=s.name,
                amount=amount,
                period=period,
                next_charge_date=ncd,
                last_charged_at=last_charged,
                due_in_days=due_in,
                is_overdue=is_overdue,
            )
        )

    return MobileSubscriptionListResponse(
        subscriptions=items,
        monthly_total=round(monthly_total),
    )


@router.get("/notifications", response_model=MobileNudgeListResponse)
@router.get("/nudges", response_model=MobileNudgeListResponse)
async def list_notifications(
    limit: int = Query(20, ge=1, le=50),
    cursor: str | None = Query(None),
    user_id: str = Depends(get_current_user),
) -> MobileNudgeListResponse:
    """Paged notification history (nudges)."""
    # Authenticated via JWT
    nudges = await container.nudge_repo.find_paged(user_id, limit=limit, cursor=cursor)

    items: list[MobileNudgeItem] = []
    for n in nudges:
        sent_at = n.sent_at
        if sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=UTC)
        items.append(
            MobileNudgeItem(
                id=str(n.id),
                type=n.nudge_type,
                title=n.title,
                body=n.message,
                sent_at=sent_at,
                was_read=n.was_read,
                metadata=n.metadata
            )
        )

    next_cursor = str(nudges[-1].id) if len(nudges) == limit else None
    return MobileNudgeListResponse(nudges=items, next_cursor=next_cursor)


@router.get("/notifications/unread-count", response_model=MobileUnreadCountResponse)
async def get_unread_count(
    user_id: str = Depends(get_current_user)
) -> MobileUnreadCountResponse:
    """Get count of unread notifications."""
    count = await container.nudge_repo.get_unread_count(user_id)
    return MobileUnreadCountResponse(unread_count=count)


@router.post("/notifications/{id}/read")
async def mark_notification_read(
    id: str,
    user_id: str = Depends(get_current_user)
):
    """Mark a specific notification as read."""
    success = await container.nudge_repo.mark_as_read(id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"status": "ok"}


@router.get("/export")
async def export_data(
    format: Literal["csv", "json"] = Query("csv"),
    user_id: str = Depends(get_current_user),
):
    """Export all transactions as CSV or JSON."""
    txns = await container.transaction_repo.find_by_user(user_id, limit=5000)

    if format == "json":
        return [t.model_dump() for t in txns]

    # CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["ID", "Date", "Amount", "Currency", "Merchant", "Category", "Direction", "Tags", "Notes"])

    for t in txns:
        writer.writerow([
            str(t.id),
            t.transaction_time.isoformat() if t.transaction_time else "",
            t.amount,
            t.currency,
            t.merchant_name or "",
            t.category_id or "",
            t.direction,
            ",".join(t.tags) if t.tags else "",
            ""
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=chiwi_export_{datetime.now().date()}.csv"}
    )


@router.post("/reports")
async def request_report(
    period: str = "last_week",
    user_id: str = Depends(get_current_user)
):
    """Trigger a weekly/monthly report on demand."""
    profile = await get_profile(user_id)
    result = await container.orchestrator.route("report", {
        "user_id": user_id,
        "period": period,
        "user_timezone": profile.timezone
    })
    return result


@router.post("/analysis")
async def request_analysis(
    user_id: str = Depends(get_current_user)
):
    """Trigger a trend analysis on demand."""
    profile = await get_profile(user_id)
    result = await container.orchestrator.route("analysis", {
        "user_id": user_id,
        "user_timezone": profile.timezone
    })
    return result


@router.delete("/profile")
async def delete_account(user_id: str = Depends(get_current_user)):
    """Delete all user data (GDPR/Data Privacy)."""
    # This should delete transactions, budgets, goals, etc.
    # For now, we'll mark as inactive or call a repository method
    await container.user_repo.delete_user_data(user_id)
    return {"status": "ok", "message": "Account data deleted"}
@router.get("/category-spending", response_model=MobileCategorySpendingResponse)
async def category_spending(
    user_id: str = Depends(get_current_user),
    period: str = Query("this_month"),
    start_date: str | None = Query(None),
    end_date: str | None = Query(None),
) -> MobileCategorySpendingResponse:
    """Category spending breakdown for a period — used for pie/bar charts.
    Supports both period labels and custom ISO8601 date ranges."""
    # Authenticated via JWT
    icons = _category_icon_map()
    profile = await get_profile(user_id)
    tz = profile.timezone

    start_dt, end_dt = resolve_date_range(period, start_date, end_date, tz)
    if start_dt is None:
        raise HTTPException(status_code=400, detail=f"Invalid date range or unsupported period: {period}")

    totals = await container.transaction_repo.aggregate_by_category(
        user_id, start_dt, end_dt
    )

    breakdown = [
        MobileCategoryItem(
            name=r["category_id"],
            icon=icons.get(r["category_id"], "❓"),
            amount=r["total"],
            tx_count=r["tx_count"],
        )
        for r in totals
    ]
    
    total_outflow = sum(r["total"] for r in totals)

    return MobileCategorySpendingResponse(
        period=period,
        total_outflow=round(total_outflow if total_outflow != 1 else 0),
        breakdown=breakdown,
    )


# ---------------------------------------------------------------------------
# Chat — conversational input from Android (mirrors Telegram chat flow)
# ---------------------------------------------------------------------------

def _inline_keyboard_to_actions(keyboard: list[list[dict]] | None) -> list[MobileChatAction]:
    """Translate Telegram-style inline_keyboard to REST-friendly actions.

    Each button ``{text, callback_data}`` is mapped to a ``MobileChatAction``
    with a structured ``action`` + ``payload`` so the Android app never has
    to parse Telegram callback_data strings.
    """
    if not keyboard:
        return []

    actions: list[MobileChatAction] = []
    for row in keyboard:
        for btn in row:
            cb = btn.get("callback_data", "")
            parts = cb.split(":", 1)
            action_id = parts[0] if parts else ""
            payload: dict = {}
            if len(parts) > 1:
                payload["id"] = parts[1]
            actions.append(
                MobileChatAction(label=btn.get("text", ""), action=action_id, payload=payload)
            )
    return actions


@router.post("/chat", response_model=MobileChatResponse)
async def mobile_chat(
    body: MobileChatRequest,
    user_id: str = Depends(get_current_user),
) -> MobileChatResponse:
    """Natural-language chat endpoint for the Android app.

    Accepts free-form text (e.g. "Ăn phở 60k hôm qua", "báo cáo tuần này")
    and routes it through the same Orchestrator pipeline as Telegram messages.
    The response is returned as structured JSON instead of a Telegram message.

    Auth: JWT must belong to an active user account.
    """
    # Authenticated via JWT

    if not body.message or not body.message.strip():
        raise HTTPException(status_code=400, detail="Message must not be empty")

    orchestrator = container.orchestrator
    profile = await get_profile(user_id)
    user_tz = profile.timezone

    payload = {
        "source": "android_chat",
        "message": body.message.strip(),
        "chat_id": "",          # no Telegram chat — responses go via REST
        "user_id": user_id,
    }

    event_type = await orchestrator.classify_event(payload)
    result = await orchestrator.route(event_type, payload)

    response_text = result.get("response_text", "")
    if not response_text:
        response_text = "Đã xử lý xong nhé!"

    return MobileChatResponse(
        status=result["status"],
        intent=result.get("intent"),
        response_text=result["response_text"],
        transaction_id=result.get("transaction_id"),
        actions=[MobileChatAction(**a) for a in result.get("inline_keyboard_mobile", [])]
    )


@router.get("/profile/link-code")
async def get_link_code(user_id: str = Depends(get_current_user)):
    """Generate a 6-digit code to link this account to Telegram."""
    import random
    import string
    from datetime import UTC, datetime, timedelta
    
    code = "".join(random.choices(string.digits, k=6))
    expires = datetime.now(UTC) + timedelta(minutes=10)
    
    await container.user_repo.update_user(user_id, {
        "link_code": code,
        "link_code_expires": expires
    })
    
    return {"code": code, "expires_at": expires}


@router.get("/profile", response_model=UserProfile)
async def get_user_profile(user_id: str = Depends(get_current_user)) -> UserProfile:
    """Return the current user's personalization profile."""
    return await get_profile(user_id)


@router.patch("/profile", response_model=UserProfile)
async def patch_user_profile(
    updates: dict,
    user_id: str = Depends(get_current_user)
) -> UserProfile:
    """Partially update personalization profile fields."""
    from src.db.models.user import UserProfileDocument
    
    existing = await container.user_repo.get_profile(user_id)
    if not existing:
        # Create default if missing
        existing = UserProfileDocument(user_id=user_id)
        await existing.insert()
    
    # Filter valid fields from updates
    allowed_fields = UserProfile.model_fields.keys()
    filtered_updates = {k: v for k, v in updates.items() if k in allowed_fields and k != "user_id"}
    
    user_updates = {}
    if "email" in filtered_updates:
        new_email = filtered_updates.pop("email")
        if new_email:
            existing_user = await container.user_repo.find_by_email(new_email)
            if existing_user and existing_user.user_id != user_id:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail="Email already in use")
        user_updates["email"] = new_email
        
    if "username" in filtered_updates:
        filtered_updates.pop("username")  # Disallow changing username via profile patch

    if user_updates:
        await container.user_repo.update_user(user_id, user_updates)
    
    if filtered_updates:
        await existing.update({"$set": filtered_updates})
        # Invalidate dashboard cache
        await container.redis.invalidate_dashboard_cache(user_id)
    
    return await get_profile(user_id)


@router.post("/logout")
async def logout(user_id: str = Depends(get_current_user)):
    """Log out the current user by clearing their refresh token hash."""
    await container.user_repo.update_user(user_id, {"refresh_token_hash": None})
    return {"status": "success", "message": "Logged out successfully"}


@router.delete("/user")
async def delete_user_account(user_id: str = Depends(get_current_user)):
    """Permanently delete user account and all related data (GDPR compliant)."""
    success = await container.user_repo.delete_user_data(user_id)
    if not success:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Invalidate caches
    await container.redis.invalidate_dashboard_cache(user_id)
    
    return {"status": "success", "message": "All user data has been permanently deleted"}
