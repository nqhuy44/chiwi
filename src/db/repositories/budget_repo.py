"""Budget repository for MongoDB operations."""

import logging
from datetime import datetime

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.budget import BudgetDocument

logger = logging.getLogger(__name__)


class BudgetRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["budgets"]

    async def insert(self, budget: BudgetDocument) -> str:
        result = await self.collection.insert_one(budget.model_dump())
        return str(result.inserted_id)

    async def find_by_user(self, user_id: str) -> list[dict]:
        cursor = (
            self.collection.find({"user_id": user_id})
            .sort("start_date", -1)
            .limit(50)
        )
        return await cursor.to_list(length=50)

    async def find_active(
        self,
        user_id: str,
        category_id: str,
        as_of: datetime,
    ) -> dict | None:
        """Return the budget covering `as_of` for (user, category), if any."""
        return await self.collection.find_one(
            {
                "user_id": user_id,
                "category_id": category_id,
                "start_date": {"$lte": as_of},
                "end_date": {"$gte": as_of},
            }
        )

    async def update_limit(self, budget_id: str, limit_amount: float) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(budget_id)},
            {"$set": {"limit_amount": limit_amount}},
        )
        return result.modified_count > 0
