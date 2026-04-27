"""Subscription repository — registered recurring charges."""

import logging
import re
from datetime import UTC, datetime, timedelta

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.subscription import SubscriptionDocument

logger = logging.getLogger(__name__)

_PERIOD_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}


class SubscriptionRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self.collection = db["subscriptions"]

    async def insert(self, sub: SubscriptionDocument) -> str:
        result = await self.collection.insert_one(sub.model_dump())
        return str(result.inserted_id)

    async def find_by_id(self, sub_id: str) -> dict | None:
        return await self.collection.find_one({"_id": ObjectId(sub_id)})

    async def find_by_user(self, user_id: str, include_inactive: bool = False) -> list[dict]:
        query: dict = {"user_id": user_id}
        if not include_inactive:
            query["is_active"] = True
        cursor = self.collection.find(query).sort("next_charge_date", 1)
        return await cursor.to_list(length=100)

    async def find_by_merchant(self, user_id: str, merchant_name: str) -> dict | None:
        """Return the active subscription whose merchant_name matches (case-insensitive)."""
        escaped = re.escape(merchant_name)
        return await self.collection.find_one(
            {
                "user_id": user_id,
                "merchant_name": {"$regex": f"^{escaped}$", "$options": "i"},
                "is_active": True,
            }
        )

    async def find_upcoming(self, user_id: str, within_hours: int = 48) -> list[dict]:
        """Active subscriptions whose next_charge_date falls within the window."""
        now = datetime.now(UTC).replace(tzinfo=None)
        cutoff = now + timedelta(hours=within_hours)
        cursor = self.collection.find(
            {
                "user_id": user_id,
                "is_active": True,
                "next_charge_date": {"$gte": now, "$lte": cutoff},
            }
        )
        return await cursor.to_list(length=50)

    async def mark_charged(self, sub_id: str, user_id: str, charged_at: datetime) -> None:
        """Advance next_charge_date by one period and record last_charged_at."""
        sub = await self.collection.find_one({"_id": ObjectId(sub_id), "user_id": user_id})
        if not sub:
            return
        period = sub.get("period", "monthly")
        days = _PERIOD_DAYS.get(period, 30)
        next_date = sub["next_charge_date"] + timedelta(days=days)
        await self.collection.update_one(
            {"_id": ObjectId(sub_id), "user_id": user_id},
            {"$set": {"last_charged_at": charged_at, "next_charge_date": next_date}},
        )
        logger.info("Subscription %s marked charged; next=%s", sub_id, next_date)

    async def deactivate(
        self,
        sub_id: str,
        user_id: str,
        reason: str = "manual",
        cancelled_at: datetime | None = None,
    ) -> None:
        """Mark a subscription inactive and record why it was cancelled."""
        await self.collection.update_one(
            {"_id": ObjectId(sub_id), "user_id": user_id},
            {
                "$set": {
                    "is_active": False,
                    "cancelled_at": cancelled_at or datetime.now(UTC),
                    "cancellation_reason": reason,
                }
            },
        )
        logger.info("Subscription %s deactivated reason=%s", sub_id, reason)
