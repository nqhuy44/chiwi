"""Subscription repository for MongoDB operations using Beanie ODM."""

import calendar
import logging
import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo
from beanie import PydanticObjectId
from dateutil.relativedelta import relativedelta
from src.db.models.subscription import SubscriptionDocument

logger = logging.getLogger(__name__)

# Day-boundary arithmetic must happen in local time so "end of month" anchors
# (e.g. anchor_day=31) resolve correctly regardless of UTC offset.
_LOCAL_TZ = ZoneInfo("Asia/Ho_Chi_Minh")


def _advance_date(current: datetime, period: str, anchor_day: int | None) -> datetime:
    """Return the next charge date, preserving the anchor day-of-month for monthly/yearly.

    Arithmetic is performed in Asia/Ho_Chi_Minh time so that an anchor_day of 31
    always lands on the last day of the target month in local time, not UTC.
    """
    if period == "weekly":
        return current + timedelta(days=7)

    # Normalise to local time for calendar arithmetic
    aware = current if current.tzinfo else current.replace(tzinfo=UTC)
    local = aware.astimezone(_LOCAL_TZ)

    if period == "yearly":
        candidate = local + relativedelta(years=1)
        if anchor_day:
            last = calendar.monthrange(candidate.year, candidate.month)[1]
            candidate = candidate.replace(day=min(anchor_day, last))
    else:
        # monthly (default)
        effective = anchor_day or local.day
        candidate = local + relativedelta(months=1)
        last = calendar.monthrange(candidate.year, candidate.month)[1]
        candidate = candidate.replace(day=min(effective, last))

    # Return in same tz-awareness as input
    result = candidate.astimezone(UTC)
    return result if current.tzinfo else result.replace(tzinfo=None)


class SubscriptionRepository:
    def __init__(self, db=None) -> None:
        pass

    async def insert(self, sub: SubscriptionDocument) -> str:
        result = await sub.insert()
        return str(result.id)

    async def find_by_id(self, sub_id: str) -> SubscriptionDocument | None:
        try:
            return await SubscriptionDocument.get(PydanticObjectId(sub_id))
        except:
            return None

    async def find_by_user(self, user_id: str, include_inactive: bool = False) -> list[SubscriptionDocument]:
        conditions = [SubscriptionDocument.user_id == user_id]
        if not include_inactive:
            conditions.append(SubscriptionDocument.is_active == True)
        return await SubscriptionDocument.find(*conditions).sort("next_charge_date").to_list()

    async def find_by_merchant(self, user_id: str, merchant_name: str) -> SubscriptionDocument | None:
        """Return the active subscription whose merchant_name matches (case-insensitive)."""
        escaped = re.escape(merchant_name)
        return await SubscriptionDocument.find_one(
            SubscriptionDocument.user_id == user_id,
            SubscriptionDocument.is_active == True,
            {"merchant_name": {"$regex": f"^{escaped}$", "$options": "i"}}
        )

    async def find_upcoming(self, user_id: str, within_hours: int = 48) -> list[SubscriptionDocument]:
        """Active subscriptions whose next_charge_date falls within the window."""
        now = datetime.now(UTC).replace(tzinfo=None)
        cutoff = now + timedelta(hours=within_hours)
        return await SubscriptionDocument.find(
            SubscriptionDocument.user_id == user_id,
            SubscriptionDocument.is_active == True,
            SubscriptionDocument.next_charge_date >= now,
            SubscriptionDocument.next_charge_date <= cutoff
        ).to_list()

    async def mark_charged(self, sub_id: str, user_id: str, charged_at: datetime) -> None:
        """Advance next_charge_date by one period and record last_charged_at."""
        sub = await self.find_by_id(sub_id)
        if not sub or sub.user_id != user_id:
            return
        
        next_date = _advance_date(sub.next_charge_date, sub.period, sub.anchor_day)
        
        await sub.set({
            SubscriptionDocument.last_charged_at: charged_at,
            SubscriptionDocument.next_charge_date: next_date
        })
        logger.info("Subscription %s marked charged; next=%s", sub_id, next_date)

    async def deactivate(
        self,
        sub_id: str,
        user_id: str,
        reason: str = "manual",
        cancelled_at: datetime | None = None,
    ) -> None:
        """Mark a subscription inactive and record why it was cancelled."""
        sub = await self.find_by_id(sub_id)
        if sub and sub.user_id == user_id:
            await sub.set({
                SubscriptionDocument.is_active: False,
                SubscriptionDocument.cancelled_at: cancelled_at or datetime.now(UTC),
                SubscriptionDocument.cancellation_reason: reason
            })
            logger.info("Subscription %s deactivated reason=%s", sub_id, reason)
