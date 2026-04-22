"""Transaction repository for MongoDB operations."""

import logging
from datetime import datetime

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.transaction import TransactionDocument

logger = logging.getLogger(__name__)


class TransactionRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.collection = db["transactions"]

    async def insert(self, transaction: TransactionDocument) -> str:
        result = await self.collection.insert_one(transaction.model_dump())
        return str(result.inserted_id)

    async def find_by_user(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[dict]:
        query: dict = {"user_id": user_id}
        if start_date or end_date:
            query["transaction_time"] = {}
            if start_date:
                query["transaction_time"]["$gte"] = start_date
            if end_date:
                query["transaction_time"]["$lte"] = end_date

        cursor = (
            self.collection.find(query)
            .sort("transaction_time", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def find_by_merchant(
        self,
        user_id: str,
        merchant_name: str,
        limit: int = 5,
    ) -> list[dict]:
        """Recent transactions for this user + merchant, newest first.

        Powers the TaggingAgent's historical memory: repeated classifications
        for the same merchant should converge to the same category.
        """
        cursor = (
            self.collection.find(
                {"user_id": user_id, "merchant_name": merchant_name}
            )
            .sort("transaction_time", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def update_category(
        self, transaction_id: str, category_id: str
    ) -> bool:
        from bson import ObjectId

        result = await self.collection.update_one(
            {"_id": ObjectId(transaction_id)},
            {
                "$set": {
                    "category_id": category_id,
                    "user_corrected": True,
                }
            },
        )
        return result.modified_count > 0
