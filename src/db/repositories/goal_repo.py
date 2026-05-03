"""Goal repository for MongoDB operations using Beanie ODM."""

import logging
from typing import Literal
from beanie import PydanticObjectId
from src.db.models.goal import GoalDocument

logger = logging.getLogger(__name__)

GoalStatus = Literal["active", "achieved", "cancelled"]


class GoalRepository:
    def __init__(self, db=None):
        pass

    async def insert(self, goal: GoalDocument) -> str:
        result = await goal.insert()
        return str(result.id)

    async def find_by_user(
        self, user_id: str, status: GoalStatus | None = "active"
    ) -> list[GoalDocument]:
        conditions = [GoalDocument.user_id == user_id]
        if status is not None:
            conditions.append(GoalDocument.status == status)
        return await GoalDocument.find(*conditions).sort("-created_at").limit(50).to_list()

    async def find_by_name(self, user_id: str, name: str, status: GoalStatus = "active") -> list[GoalDocument]:
        import re
        return await GoalDocument.find(
            GoalDocument.user_id == user_id,
            GoalDocument.status == status,
            {"name": {"$regex": re.escape(name), "$options": "i"}}
        ).to_list()

    async def update_progress(self, goal_id: str, user_id: str, current_amount: float) -> bool:
        try:
            goal = await GoalDocument.get(PydanticObjectId(goal_id))
            if goal and goal.user_id == user_id:
                await goal.set({GoalDocument.current_amount: current_amount})
                return True
        except:
            pass
        return False

    async def set_status(self, goal_id: str, user_id: str, status: GoalStatus) -> bool:
        try:
            goal = await GoalDocument.get(PydanticObjectId(goal_id))
            if goal and goal.user_id == user_id:
                await goal.set({GoalDocument.status: status})
                return True
        except:
            pass
        return False

    async def find_by_id(self, goal_id: str, user_id: str) -> GoalDocument | None:
        try:
            goal = await GoalDocument.get(PydanticObjectId(goal_id))
            if goal and goal.user_id == user_id:
                return goal
        except:
            pass
        return None

    async def delete(self, goal_id: str, user_id: str) -> bool:
        try:
            goal = await GoalDocument.get(PydanticObjectId(goal_id))
            if goal and goal.user_id == user_id:
                await goal.delete()
                return True
        except:
            pass
        return False

    async def update(self, goal_id: str, user_id: str, updates: dict) -> bool:
        try:
            goal = await GoalDocument.get(PydanticObjectId(goal_id))
            if goal and goal.user_id == user_id:
                await goal.update({"$set": updates})
                return True
        except:
            pass
        return False
