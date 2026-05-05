"""Transaction repository for MongoDB operations using Beanie ODM."""

import logging
from datetime import datetime
from beanie import PydanticObjectId
from src.db.models.transaction import TransactionDocument

logger = logging.getLogger(__name__)


class TransactionRepository:
    def __init__(self, db=None):
        pass

    async def insert(self, transaction: TransactionDocument) -> str:
        result = await transaction.insert()
        return str(result.id)

    async def find_by_id(self, transaction_id: str) -> TransactionDocument | None:
        try:
            return await TransactionDocument.get(PydanticObjectId(transaction_id))
        except:
            return None

    async def find_by_user(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        limit: int = 50,
    ) -> list[TransactionDocument]:
        conditions = [TransactionDocument.user_id == user_id]
        if start_date:
            conditions.append(TransactionDocument.transaction_time >= start_date)
        if end_date:
            conditions.append(TransactionDocument.transaction_time <= end_date)

        return await TransactionDocument.find(*conditions).sort("-transaction_time").limit(limit).to_list()

    async def find_by_merchant(
        self,
        user_id: str,
        merchant_name: str,
        limit: int = 5,
    ) -> list[TransactionDocument]:
        return await TransactionDocument.find(
            TransactionDocument.user_id == user_id,
            TransactionDocument.merchant_name == merchant_name
        ).sort("-transaction_time").limit(limit).to_list()

    async def lock(self, transaction_id: str, user_id: str) -> bool:
        txn = await self.find_by_id(transaction_id)
        if txn and txn.user_id == user_id:
            await txn.set({TransactionDocument.locked: True})
            return True
        return False

    async def delete(self, transaction_id: str, user_id: str) -> bool:
        txn = await self.find_by_id(transaction_id)
        if txn and txn.user_id == user_id:
            if txn.locked:
                return False
            await txn.delete()
            return True
        return False

    async def update_category(
        self, transaction_id: str, category_id: str, user_id: str
    ) -> bool:
        txn = await self.find_by_id(transaction_id)
        if txn and txn.user_id == user_id:
            await txn.set({
                TransactionDocument.category_id: category_id,
                TransactionDocument.user_corrected: True
            })
            return True
        return False

    async def set_subscription_id(
        self, transaction_id: str, subscription_id: str
    ) -> bool:
        txn = await self.find_by_id(transaction_id)
        if txn:
            await txn.set({TransactionDocument.subscription_id: subscription_id})
            return True
        return False

    async def find_by_subscription(
        self, user_id: str, subscription_id: str, limit: int = 50
    ) -> list[TransactionDocument]:
        from beanie import PydanticObjectId
        try:
            obj_id = PydanticObjectId(subscription_id)
            selector = {"subscription_id": {"$in": [subscription_id, obj_id]}}
        except Exception:
            selector = {"subscription_id": subscription_id}
            
        return await TransactionDocument.find(
            TransactionDocument.user_id == user_id,
            selector
        ).sort("-transaction_time").limit(limit).to_list()

    async def find_by_user_with_subscription(
        self,
        user_id: str,
        start_date: datetime | None = None,
        limit: int = 20,
    ) -> list[TransactionDocument]:
        """Fetch transactions linked to any subscription for a user."""
        conditions = [
            TransactionDocument.user_id == user_id,
            TransactionDocument.subscription_id != None
        ]
        if start_date:
            conditions.append(TransactionDocument.transaction_time >= start_date)

        return await TransactionDocument.find(*conditions).sort("-transaction_time").limit(limit).to_list()

    async def find_paged(
        self,
        user_id: str,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        category_id: str | None = None,
        direction: str | None = None,
        limit: int = 20,
        after_id: str | None = None,
        goal_id: str | None = None,
        subscription_id: str | None = None,
    ) -> list[TransactionDocument]:
        from beanie import PydanticObjectId
        from beanie.operators import In

        conditions = [TransactionDocument.user_id == user_id]
        if start_date:
            conditions.append(TransactionDocument.transaction_time >= start_date)
        if end_date:
            conditions.append(TransactionDocument.transaction_time <= end_date)
        if category_id:
            conditions.append(TransactionDocument.category_id == category_id)
        if direction:
            conditions.append(TransactionDocument.direction == direction)
        if goal_id:
            conditions.append(TransactionDocument.goal_id == goal_id)

        if subscription_id:
            try:
                obj_id = PydanticObjectId(subscription_id)
                conditions.append(In(TransactionDocument.subscription_id, [subscription_id, obj_id]))
            except Exception:
                conditions.append(TransactionDocument.subscription_id == subscription_id)
        
        if after_id:
            try:
                conditions.append(TransactionDocument.id < PydanticObjectId(after_id))
            except Exception:
                pass

        return await TransactionDocument.find(*conditions).sort("-transaction_time", "-id").limit(limit).to_list()

    async def find_by_goal(self, user_id: str, goal_id: str, limit: int = 50) -> list[TransactionDocument]:
        return await TransactionDocument.find(
            TransactionDocument.user_id == user_id,
            TransactionDocument.goal_id == goal_id
        ).sort("-transaction_time").limit(limit).to_list()

    async def count_in_period(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        category_id: str | None = None,
        direction: str | None = None,
        goal_id: str | None = None,
        subscription_id: str | None = None,
    ) -> int:
        from beanie import PydanticObjectId
        from beanie.operators import In

        conditions = [
            TransactionDocument.user_id == user_id,
            TransactionDocument.transaction_time >= start_date,
            TransactionDocument.transaction_time <= end_date,
        ]
        if category_id:
            conditions.append(TransactionDocument.category_id == category_id)
        if direction:
            conditions.append(TransactionDocument.direction == direction)
        if goal_id:
            conditions.append(TransactionDocument.goal_id == goal_id)
        
        if subscription_id:
            try:
                obj_id = PydanticObjectId(subscription_id)
                conditions.append(In(TransactionDocument.subscription_id, [subscription_id, obj_id]))
            except Exception:
                conditions.append(TransactionDocument.subscription_id == subscription_id)

        return await TransactionDocument.find(*conditions).count()

    async def aggregate_by_category(
        self,
        user_id: str,
        start_date: datetime,
        end_date: datetime,
        direction: str = "outflow",
    ) -> list[dict]:
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
        
        raw = await TransactionDocument.aggregate(pipeline).to_list(length=100)
        return [
            {
                "category_id": r["_id"] or "Khác",
                "total": round(r["total"]),
                "tx_count": r["tx_count"],
            }
            for r in raw
        ]
