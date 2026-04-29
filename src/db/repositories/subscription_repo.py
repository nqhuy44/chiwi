"""Subscription repository for MongoDB operations using Beanie ODM."""

import logging
import re
from datetime import UTC, datetime, timedelta
from beanie import PydanticObjectId
from src.db.models.subscription import SubscriptionDocument

logger = logging.getLogger(__name__)

_PERIOD_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}


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
        
        days = _PERIOD_DAYS.get(sub.period, 30)
        next_date = sub.next_charge_date + timedelta(days=days)
        
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
