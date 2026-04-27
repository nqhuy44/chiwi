"""Budget repository — category spending limits and their change history."""

import logging
from datetime import UTC, datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.budget import BudgetDocument, BudgetEventDocument

logger = logging.getLogger(__name__)


def effective_limit(budget: dict, now: datetime | None = None) -> float:
    """Return the limit that applies right now for a budget document.

    If a temp_limit is set and hasn't expired, it takes precedence.
    Otherwise the base limit_amount is used.
    """
    now = now or datetime.now(UTC).replace(tzinfo=None)
    temp = budget.get("temp_limit")
    expires = budget.get("temp_limit_expires_at")
    if temp and expires:
        exp = expires.replace(tzinfo=None) if expires.tzinfo else expires
        if now <= exp:
            return float(temp)
    return float(budget["limit_amount"])


class BudgetRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["budgets"]

    async def insert(self, budget: BudgetDocument) -> str:
        result = await self.collection.insert_one(budget.model_dump())
        return str(result.inserted_id)

    async def find_by_id(self, budget_id: str) -> dict | None:
        return await self.collection.find_one({"_id": ObjectId(budget_id)})

    async def find_by_user(self, user_id: str, include_inactive: bool = False) -> list[dict]:
        query: dict = {"user_id": user_id}
        if not include_inactive:
            query["is_active"] = True
        cursor = self.collection.find(query).sort("category_id", 1)
        return await cursor.to_list(length=100)

    async def find_active(self, user_id: str, category_id: str, as_of: datetime) -> dict | None:
        """Return the active budget for (user, category) that covers `as_of`."""
        return await self.collection.find_one(
            {
                "user_id": user_id,
                "category_id": category_id,
                "is_active": True,
            }
        )

    async def update_limit(
        self,
        budget_id: str,
        user_id: str,
        limit_amount: float,
    ) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id), "user_id": user_id},
            {"$set": {"limit_amount": limit_amount, "updated_at": datetime.now(UTC)}},
        )
        return result.modified_count > 0

    async def set_temp_override(
        self,
        budget_id: str,
        user_id: str,
        temp_limit: float,
        expires_at: datetime,
        reason: str | None = None,
    ) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id), "user_id": user_id},
            {
                "$set": {
                    "temp_limit": temp_limit,
                    "temp_limit_expires_at": expires_at,
                    "temp_limit_reason": reason,
                }
            },
        )
        return result.modified_count > 0

    async def clear_temp_override(self, budget_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id), "user_id": user_id},
            {"$set": {"temp_limit": None, "temp_limit_expires_at": None, "temp_limit_reason": None}},
        )
        return result.modified_count > 0

    async def silence(self, budget_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id), "user_id": user_id},
            {"$set": {"is_silenced": True, "silenced_at": datetime.now(UTC)}},
        )
        return result.modified_count > 0

    async def unsilence(self, budget_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id), "user_id": user_id},
            {"$set": {"is_silenced": False, "silenced_at": None}},
        )
        return result.modified_count > 0

    async def deactivate(self, budget_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id), "user_id": user_id},
            {"$set": {"is_active": False, "updated_at": datetime.now(UTC)}},
        )
        return result.modified_count > 0

    async def reactivate(self, budget_id: str, user_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id), "user_id": user_id},
            {"$set": {"is_active": True, "updated_at": datetime.now(UTC)}},
        )
        return result.modified_count > 0


class BudgetEventRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["budget_events"]

    async def insert(self, event: BudgetEventDocument) -> str:
        result = await self.collection.insert_one(event.model_dump())
        return str(result.inserted_id)

    async def find_by_budget(self, budget_id: str, limit: int = 50) -> list[dict]:
        cursor = (
            self.collection.find({"budget_id": budget_id})
            .sort("created_at", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def find_by_user(
        self,
        user_id: str,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        query: dict = {"user_id": user_id}
        if event_type:
            query["event_type"] = event_type
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def count_by_type(
        self,
        user_id: str,
        category_id: str,
        event_type: str,
        since: datetime,
    ) -> int:
        """Count how many times a specific event type fired for a budget category
        since a given datetime. Used to detect behavioral patterns."""
        return await self.collection.count_documents(
            {
                "user_id": user_id,
                "category_id": category_id,
                "event_type": event_type,
                "created_at": {"$gte": since},
            }
        )
