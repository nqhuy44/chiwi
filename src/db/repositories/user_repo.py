"""User repository for MongoDB operations."""

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.db.models.user import UserDocument, UserProfileDocument


class UserRepository:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.users = db["users"]
        self.profiles = db["user_profiles"]

    async def find_by_telegram_id(self, telegram_user_id: str) -> dict | None:
        return await self.users.find_one(
            {"telegram_user_id": telegram_user_id}
        )

    async def create_user(self, user: UserDocument) -> str:
        result = await self.users.insert_one(user.model_dump())
        return str(result.inserted_id)

    async def get_profile(self, user_id: str) -> dict | None:
        return await self.profiles.find_one({"user_id": user_id})

    async def update_profile(
        self, user_id: str, profile: UserProfileDocument
    ) -> bool:
        result = await self.profiles.update_one(
            {"user_id": user_id},
            {"$set": profile.model_dump()},
            upsert=True,
        )
        return result.acknowledged
