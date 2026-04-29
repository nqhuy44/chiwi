"""Nudge repository for MongoDB operations using Beanie ODM."""

import logging
from datetime import UTC, datetime, timedelta
from src.db.models.nudge import NudgeDocument

logger = logging.getLogger(__name__)


class NudgeRepository:
    def __init__(self, db=None):
        pass

    async def insert(self, nudge: NudgeDocument) -> str:
        result = await nudge.insert()
        return str(result.id)

    async def count_since(self, user_id: str, since: datetime) -> int:
        return await NudgeDocument.find(
            NudgeDocument.user_id == user_id,
            NudgeDocument.sent_at >= since
        ).count()

    async def find_recent(
        self, user_id: str, hours: int = 24, limit: int = 20
    ) -> list[NudgeDocument]:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        return await NudgeDocument.find(
            NudgeDocument.user_id == user_id,
            NudgeDocument.sent_at >= cutoff
        ).sort("-sent_at").limit(limit).to_list()

    async def mark_as_read(self, nudge_id: str, user_id: str) -> bool:
        from beanie import PydanticObjectId
        try:
            nudge = await NudgeDocument.get(PydanticObjectId(nudge_id))
            if nudge and nudge.user_id == user_id:
                await nudge.set({
                    NudgeDocument.was_read: True,
                    NudgeDocument.updated_at: datetime.now(UTC)
                })
                return True
        except:
            pass
        return False

    async def get_unread_count(self, user_id: str) -> int:
        return await NudgeDocument.find(
            NudgeDocument.user_id == user_id,
            NudgeDocument.was_read == False
        ).count()

    async def find_paged(
        self, user_id: str, limit: int = 20, cursor: str | None = None
    ) -> list[NudgeDocument]:
        from beanie import PydanticObjectId
        conditions = [NudgeDocument.user_id == user_id]
        if cursor:
            try:
                conditions.append(NudgeDocument.id < PydanticObjectId(cursor))
            except Exception:
                pass
        return await NudgeDocument.find(*conditions).sort("-sent_at", "-id").limit(limit).to_list()

    async def has_recent_type(
        self, user_id: str, nudge_type: str, hours: int = 24
    ) -> bool:
        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        count = await NudgeDocument.find(
            NudgeDocument.user_id == user_id,
            NudgeDocument.nudge_type == nudge_type,
            NudgeDocument.sent_at >= cutoff
        ).count()
        return count > 0
