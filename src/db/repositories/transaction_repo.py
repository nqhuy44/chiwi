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

    async def find_by_id(self, transaction_id: str) -> dict | None:
        from bson import ObjectId

        return await self.collection.find_one({"_id": ObjectId(transaction_id)})

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

    async def lock(self, transaction_id: str, user_id: str) -> bool:
        from bson import ObjectId

        result = await self.collection.update_one(
            {"_id": ObjectId(transaction_id), "user_id": user_id},
            {"$set": {"locked": True}},
        )
        return result.modified_count > 0

    async def delete(self, transaction_id: str, user_id: str) -> bool:
        from bson import ObjectId

        result = await self.collection.delete_one(
            {"_id": ObjectId(transaction_id), "user_id": user_id}
        )
        return result.deleted_count > 0

    async def update_category(
        self, transaction_id: str, category_id: str, user_id: str
    ) -> bool:
        from bson import ObjectId

        result = await self.collection.update_one(
            {"_id": ObjectId(transaction_id), "user_id": user_id},
            {
                "$set": {
                    "category_id": category_id,
                    "user_corrected": True,
                }
            },
        )
        return result.modified_count > 0

    async def set_subscription_id(
        self, transaction_id: str, subscription_id: str
    ) -> bool:
        from bson import ObjectId

        result = await self.collection.update_one(
            {"_id": ObjectId(transaction_id)},
            {"$set": {"subscription_id": subscription_id}},
        )
        return result.modified_count > 0

    async def find_by_subscription(
        self, user_id: str, subscription_id: str, limit: int = 50
    ) -> list[dict]:
        """All transactions linked to a specific subscription, newest first."""
        cursor = (
            self.collection.find(
                {"user_id": user_id, "subscription_id": subscription_id}
            )
            .sort("transaction_time", -1)
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def find_paged(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        category_id: str | None = None,
        direction: str | None = None,
        limit: int = 20,
        after_id: str | None = None,
    ) -> list[dict]:
        """Cursor-based paginated transaction list for the mobile API.

        ``after_id`` is the string _id of the last item on the previous page.
        Sort order is insertion time descending (ObjectId desc) which is
        equivalent to chronological order for non-backdated transactions.
        """
        from bson import ObjectId
        from bson.errors import InvalidId

        query: dict = {"user_id": user_id}
        if start_date or end_date:
            query["transaction_time"] = {}
            if start_date:
                query["transaction_time"]["$gte"] = start_date
            if end_date:
                query["transaction_time"]["$lte"] = end_date
        if category_id:
            query["category_id"] = category_id
        if direction:
            query["direction"] = direction
        if after_id:
            try:
                query["_id"] = {"$lt": ObjectId(after_id)}
            except (InvalidId, TypeError):
                pass

        cursor = (
            self.collection.find(query)
            .sort([("transaction_time", -1), ("_id", -1)])
            .limit(limit)
        )
        return await cursor.to_list(length=limit)

    async def count_in_period(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        category_id: str | None = None,
        direction: str | None = None,
    ) -> int:
        """Total count of transactions matching filters — used for pagination metadata."""
        query: dict = {
            "user_id": user_id,
            "transaction_time": {"$gte": start_date, "$lte": end_date},
        }
        if category_id:
            query["category_id"] = category_id
        if direction:
            query["direction"] = direction
        return await self.collection.count_documents(query)

    async def aggregate_by_category(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        direction: str = "outflow",
    ) -> list[dict]:
        """MongoDB aggregation: spending totals grouped by category for a period.

        Returns list of {"category_id": str, "total": float, "tx_count": int}
        sorted by total descending.
        """
        pipeline = [
            {
                "$match": {
                    "user_id": user_id,
                    "direction": direction,
                    "transaction_time": {"$gte": start_date, "$lte": end_date},
                }
            },
            {
                "$group": {
                    "_id": "$category_id",
                    "total": {"$sum": "$amount"},
                    "tx_count": {"$sum": 1},
                }
            },
            {"$sort": {"total": -1}},
        ]
        raw = await self.collection.aggregate(pipeline).to_list(length=100)
        return [
            {
                "category_id": r["_id"] or "Khác",
                "total": round(r["total"]),
                "tx_count": r["tx_count"],
            }
            for r in raw
        ]
