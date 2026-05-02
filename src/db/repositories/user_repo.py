"""User repository for MongoDB operations using Beanie ODM."""

from src.db.models.user import UserDocument, UserProfileDocument


class UserRepository:
    def __init__(self, db=None):
        # db is handled by Beanie init_beanie, but kept for signature compatibility
        pass

    async def find_by_id(self, user_id: str) -> UserDocument | None:
        return await UserDocument.find_one(UserDocument.user_id == user_id)

    async def create_user(self, user: UserDocument) -> str:
        result = await user.insert()
        return str(result.id)

    async def update_user(self, user_id: str, update_data: dict) -> bool:
        user = await self.find_by_id(user_id)
        if not user:
            return False
        await user.update({"$set": update_data})
        return True

    async def get_profile(self, user_id: str) -> UserProfileDocument | None:
        return await UserProfileDocument.find_one(UserProfileDocument.user_id == user_id)

    async def update_profile(
        self, user_id: str, profile: UserProfileDocument
    ) -> bool:
        existing = await self.get_profile(user_id)
        if existing:
            await existing.update({"$set": profile.model_dump(exclude={"id"})})
        else:
            await profile.insert()
        return True

    async def list_active_user_ids(self) -> list[str]:
        users = await UserDocument.find(UserDocument.is_active == True).to_list()
        return [u.user_id for u in users]

    async def find_by_username(self, username: str) -> UserDocument | None:
        """Find user by their unique login username."""
        return await UserDocument.find_one(UserDocument.username == username)

    async def find_by_telegram_id(self, telegram_id: str) -> UserDocument | None:
        """Find user by their linked Telegram ID."""
        return await UserDocument.find_one(UserDocument.telegram_id == str(telegram_id))

    async def find_by_chat_id(self, chat_id: str) -> UserDocument | None:
        """Find user by their linked Telegram chat ID (Alias for find_by_telegram_id)."""
        return await self.find_by_telegram_id(chat_id)

    async def find_by_link_code(self, code: str) -> UserDocument | None:
        """Find user by an active linking code."""
        from datetime import UTC, datetime
        return await UserDocument.find_one(
            UserDocument.link_code == code,
            UserDocument.link_code_expires > datetime.now(UTC)
        )

    async def delete_user_data(self, user_id: str) -> bool:
        """Wipe all user-related data (Privacy/GDPR requirement)."""
        from src.db.models.budget import BudgetDocument
        from src.db.models.correction import CorrectionDocument
        from src.db.models.goal import GoalDocument
        from src.db.models.nudge import NudgeDocument
        from src.db.models.subscription import SubscriptionDocument
        from src.db.models.transaction import TransactionDocument

        # Delete from all specialized collections
        await TransactionDocument.find(TransactionDocument.user_id == user_id).delete()
        await BudgetDocument.find(BudgetDocument.user_id == user_id).delete()
        await GoalDocument.find(GoalDocument.user_id == user_id).delete()
        await NudgeDocument.find(NudgeDocument.user_id == user_id).delete()
        await SubscriptionDocument.find(SubscriptionDocument.user_id == user_id).delete()
        await CorrectionDocument.find(CorrectionDocument.user_id == user_id).delete()
        await UserProfileDocument.find(UserProfileDocument.user_id == user_id).delete()

        # Finally delete the user account itself
        user = await self.find_by_id(user_id)
        if user:
            await user.delete()
        return True
