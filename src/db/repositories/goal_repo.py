"""Goal repository for MongoDB operations."""

import logging
from typing import Literal

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.goal import GoalDocument

logger = logging.getLogger(__name__)

GoalStatus = Literal["active", "achieved", "cancelled"]


class GoalRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["goals"]

    async def insert(self, goal: GoalDocument) -> str:
        result = await self.collection.insert_one(goal.model_dump())
        return str(result.inserted_id)

    async def find_by_user(
        self, user_id: str, status: GoalStatus | None = "active"
    ) -> list[dict]:
        query: dict = {"user_id": user_id}
        if status is not None:
            query["status"] = status
        cursor = (
            self.collection.find(query)
            .sort("created_at", -1)
            .limit(50)
        )
        return await cursor.to_list(length=50)

    async def update_progress(self, goal_id: str, current_amount: float) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(goal_id)},
            {"$set": {"current_amount": current_amount}},
        )
        return result.modified_count > 0

    async def set_status(self, goal_id: str, status: GoalStatus) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(goal_id)},
            {"$set": {"status": status}},
        )
        return result.modified_count > 0
