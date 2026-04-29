"""Correction repository for MongoDB operations using Beanie ODM."""

import logging
from src.db.models.correction import CorrectionDocument

logger = logging.getLogger(__name__)


class CorrectionRepository:
    def __init__(self, db=None):
        pass

    async def insert(self, correction: CorrectionDocument) -> str:
        result = await correction.insert()
        return str(result.id)

    async def find_recent_for_merchant(
        self, user_id: str, merchant_name: str, limit: int = 3
    ) -> list[CorrectionDocument]:
        return await CorrectionDocument.find(
            CorrectionDocument.user_id == user_id,
            CorrectionDocument.merchant_name == merchant_name
        ).sort("-created_at").limit(limit).to_list()
