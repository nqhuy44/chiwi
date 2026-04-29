"""Budget repository for MongoDB operations using Beanie ODM."""

import logging
from datetime import UTC, datetime
from beanie import PydanticObjectId
from src.db.models.budget import BudgetDocument, BudgetEventDocument

logger = logging.getLogger(__name__)


def effective_limit(budget: BudgetDocument, now: datetime | None = None) -> float:
    """Return the limit that applies right now for a budget document."""
    now = now or datetime.now(UTC).replace(tzinfo=None)
    temp = budget.temp_limit
    expires = budget.temp_limit_expires_at
    if temp and expires:
        exp = expires.replace(tzinfo=None) if expires.tzinfo else expires
        if now <= exp:
            return float(temp)
    return float(budget.limit_amount)


class BudgetRepository:
    def __init__(self, db=None):
        pass

    async def insert(self, budget: BudgetDocument) -> str:
        result = await budget.insert()
        return str(result.id)

    async def find_by_id(self, budget_id: str) -> BudgetDocument | None:
        try:
            return await BudgetDocument.get(PydanticObjectId(budget_id))
        except:
            return None

    async def find_by_user(self, user_id: str, include_inactive: bool = False) -> list[BudgetDocument]:
        conditions = [BudgetDocument.user_id == user_id]
        if not include_inactive:
            conditions.append(BudgetDocument.is_active == True)
        return await BudgetDocument.find(*conditions).sort("category_id").to_list()

    async def find_active(self, user_id: str, category_id: str, as_of: datetime) -> BudgetDocument | None:
        return await BudgetDocument.find_one(
            BudgetDocument.user_id == user_id,
            BudgetDocument.category_id == category_id,
            BudgetDocument.is_active == True
        )

    async def update_limit(
        self,
        budget_id: str,
        user_id: str,
        limit_amount: float,
    ) -> bool:
        budget = await self.find_by_id(budget_id)
        if budget and budget.user_id == user_id:
            await budget.set({
                BudgetDocument.limit_amount: limit_amount,
                BudgetDocument.updated_at: datetime.now(UTC)
            })
            return True
        return False

    async def set_temp_override(
        self,
        budget_id: str,
        user_id: str,
        temp_limit: float,
        expires_at: datetime,
        reason: str | None = None,
    ) -> bool:
        budget = await self.find_by_id(budget_id)
        if budget and budget.user_id == user_id:
            await budget.set({
                BudgetDocument.temp_limit: temp_limit,
                BudgetDocument.temp_limit_expires_at: expires_at,
                BudgetDocument.temp_limit_reason: reason
            })
            return True
        return False

    async def clear_temp_override(self, budget_id: str, user_id: str) -> bool:
        budget = await self.find_by_id(budget_id)
        if budget and budget.user_id == user_id:
            await budget.set({
                BudgetDocument.temp_limit: None,
                BudgetDocument.temp_limit_expires_at: None,
                BudgetDocument.temp_limit_reason: None
            })
            return True
        return False

    async def silence(self, budget_id: str, user_id: str) -> bool:
        budget = await self.find_by_id(budget_id)
        if budget and budget.user_id == user_id:
            await budget.set({
                BudgetDocument.is_silenced: True,
                BudgetDocument.silenced_at: datetime.now(UTC)
            })
            return True
        return False

    async def unsilence(self, budget_id: str, user_id: str) -> bool:
        budget = await self.find_by_id(budget_id)
        if budget and budget.user_id == user_id:
            await budget.set({
                BudgetDocument.is_silenced: False,
                BudgetDocument.silenced_at: None
            })
            return True
        return False

    async def deactivate(self, budget_id: str, user_id: str) -> bool:
        budget = await self.find_by_id(budget_id)
        if budget and budget.user_id == user_id:
            await budget.set({
                BudgetDocument.is_active: False,
                BudgetDocument.updated_at: datetime.now(UTC)
            })
            return True
        return False

    async def reactivate(self, budget_id: str, user_id: str) -> bool:
        budget = await self.find_by_id(budget_id)
        if budget and budget.user_id == user_id:
            await budget.set({
                BudgetDocument.is_active: True,
                BudgetDocument.updated_at: datetime.now(UTC)
            })
            return True
        return False


class BudgetEventRepository:
    def __init__(self, db=None):
        pass

    async def insert(self, event: BudgetEventDocument) -> str:
        result = await event.insert()
        return str(result.id)

    async def find_by_budget(self, budget_id: str, limit: int = 50) -> list[BudgetEventDocument]:
        return await BudgetEventDocument.find(
            BudgetEventDocument.budget_id == budget_id
        ).sort("-created_at").limit(limit).to_list()

    async def find_by_user(
        self,
        user_id: str,
        event_type: str | None = None,
        limit: int = 100,
    ) -> list[BudgetEventDocument]:
        conditions = [BudgetEventDocument.user_id == user_id]
        if event_type:
            conditions.append(BudgetEventDocument.event_type == event_type)
        return await BudgetEventDocument.find(*conditions).sort("-created_at").limit(limit).to_list()

    async def count_by_type(
        self,
        user_id: str,
        category_id: str,
        event_type: str,
        since: datetime,
    ) -> int:
        return await BudgetEventDocument.find(
            BudgetEventDocument.user_id == user_id,
            BudgetEventDocument.category_id == category_id,
            BudgetEventDocument.event_type == event_type,
            BudgetEventDocument.created_at >= since
        ).count()
