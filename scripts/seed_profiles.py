import asyncio
import json
import logging
import os
import sys

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.core.dependencies import container
from src.db.models.user import UserDocument, UserProfileDocument
from src.core.security import get_password_hash

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROFILES_FILE = "config/user_profiles.json"
DEFAULT_PASSWORD = "changeme123"

async def seed():
    logger.info("Starting profile migration to MongoDB...")
    await container.startup()
    
    if not os.path.exists(PROFILES_FILE):
        logger.error(f"Profiles file not found: {PROFILES_FILE}")
        return

    with open(PROFILES_FILE, "r") as f:
        profiles_data = json.load(f)

    user_repo = container.user_repo
    hashed_pwd = get_password_hash(DEFAULT_PASSWORD)

    for user_id, profile_dict in profiles_data.items():
        if user_id == "default":
            continue

        # Check if user exists
        existing = await user_repo.find_by_id(user_id)
        if existing:
            logger.info(f"User {user_id} already exists, skipping identity creation.")
        else:
            # Create User Identity
            user_doc = UserDocument(
                user_id=user_id,
                username=user_id,  # Use user_id as username for now
                hashed_password=hashed_pwd,
                full_name=profile_dict.get("occupation", "ChiWi User")
            )
            await user_repo.create_user(user_doc)
            logger.info(f"Created identity for user {user_id}")

        # Create/Update Profile
        profile_doc = UserProfileDocument(
            user_id=user_id,
            occupation=profile_dict.get("occupation", ""),
            hobbies=profile_dict.get("hobbies", []),
            interests=profile_dict.get("interests", []),
            communication_tone=profile_dict.get("communication_tone", "friendly"),
            nudge_frequency=profile_dict.get("nudge_frequency", "daily"),
            language=profile_dict.get("language", "vi"),
            timezone=profile_dict.get("timezone", "Asia/Ho_Chi_Minh"),
            chat_id=profile_dict.get("chat_id", ""),
            extras=profile_dict.get("extras", {})
        )
        await user_repo.update_profile(user_id, profile_doc)
        logger.info(f"Seeded profile for user {user_id}")

    logger.info("Migration complete.")

if __name__ == "__main__":
    asyncio.run(seed())
