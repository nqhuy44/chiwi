"""
Migration script: Raw MongoDB → Beanie ODM schema.

Strategy: Use raw motor operations ($set / $unset / $rename) to patch
documents **before** Beanie tries to validate them. This avoids
ValidationError when old documents are missing required fields or
contain deprecated fields.

Idempotent — safe to run multiple times.
"""

import asyncio
import logging
from datetime import UTC, datetime

from motor.motor_asyncio import AsyncIOMotorClient

from src.core.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

NOW = datetime.now(UTC)


async def migrate():
    logger.info("Starting migration to Beanie ODM schema...")
    client = AsyncIOMotorClient(settings.mongodb_uri)
    db = client[settings.mongodb_db_name]

    # ── 1. Users ──────────────────────────────────────────────────────
    users_col = db["users"]
    count = await users_col.count_documents({})
    logger.info(f"Users collection: {count} documents")

    # 1a. Backfill `username` from `user_id` where missing
    result = await users_col.update_many(
        {"username": {"$exists": False}},
        [{"$set": {"username": "$user_id"}}],
    )
    if result.modified_count:
        logger.info(f"  Backfilled username for {result.modified_count} users")

    # 1b. Rename `display_name` → `full_name` where applicable
    result = await users_col.update_many(
        {"display_name": {"$exists": True}},
        {"$rename": {"display_name": "full_name"}},
    )
    if result.modified_count:
        logger.info(f"  Renamed display_name → full_name for {result.modified_count} users")

    # 1c. Ensure all required fields have defaults
    defaults = {
        "hashed_password": None,
        "refresh_token_hash": None,
        "full_name": "",
        "telegram_chat_id": None,
        "link_code": None,
        "link_code_expires": None,
        "is_active": True,
        "created_at": NOW,
        "updated_at": NOW,
    }
    for field, default in defaults.items():
        result = await users_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} users")

    # 1d. Remove deprecated fields
    deprecated_user_fields = ["channels"]
    for field in deprecated_user_fields:
        result = await users_col.update_many(
            {field: {"$exists": True}},
            {"$unset": {field: ""}},
        )
        if result.modified_count:
            logger.info(f"  Removed deprecated field '{field}' from {result.modified_count} users")

    # ── 2. User Profiles ─────────────────────────────────────────────
    profiles_col = db["user_profiles"]
    count = await profiles_col.count_documents({})
    logger.info(f"User profiles collection: {count} documents")

    profile_defaults = {
        "timezone": "Asia/Ho_Chi_Minh",
        "occupation": "",
        "hobbies": [],
        "interests": [],
        "communication_tone": "friendly",
        "nudge_frequency": "daily",
        "language": "vi",
        "extras": {},
        "updated_at": NOW,
    }
    for field, default in profile_defaults.items():
        result = await profiles_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} profiles")

    # Remove deprecated profile fields
    deprecated_profile_fields = ["chat_id"]
    for field in deprecated_profile_fields:
        result = await profiles_col.update_many(
            {field: {"$exists": True}},
            {"$unset": {field: ""}},
        )
        if result.modified_count:
            logger.info(f"  Removed deprecated field '{field}' from {result.modified_count} profiles")

    # ── 3. Transactions ──────────────────────────────────────────────
    txn_col = db["transactions"]
    count = await txn_col.count_documents({})
    logger.info(f"Transactions collection: {count} documents")

    txn_defaults = {
        "currency": "VND",
        "merchant_name": None,
        "category_id": None,
        "tags": [],
        "agent_confidence": "low",
        "user_corrected": False,
        "locked": False,
        "ai_metadata": {},
        "subscription_id": None,
        "created_at": NOW,
    }
    for field, default in txn_defaults.items():
        result = await txn_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} transactions")

    # ── 4. Nudges ────────────────────────────────────────────────────
    nudge_col = db["nudges"]
    count = await nudge_col.count_documents({})
    logger.info(f"Nudges collection: {count} documents")

    nudge_defaults = {
        "title": "ChiWi Insight",
        "channel": "both",
        "metadata": {},
        "trigger_reason": "",
        "was_read": False,
        "user_acted": False,
        "sent_at": NOW,
        "updated_at": NOW,
    }
    for field, default in nudge_defaults.items():
        result = await nudge_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} nudges")

    # ── 5. Corrections ───────────────────────────────────────────────
    corr_col = db["corrections"]
    count = await corr_col.count_documents({})
    logger.info(f"Corrections collection: {count} documents")

    corr_defaults = {
        "merchant_name": None,
        "old_category": None,
        "created_at": NOW,
    }
    for field, default in corr_defaults.items():
        result = await corr_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} corrections")

    # ── 6. Budgets ───────────────────────────────────────────────────
    budget_col = db["budgets"]
    count = await budget_col.count_documents({})
    logger.info(f"Budgets collection: {count} documents")

    budget_defaults = {
        "is_active": True,
        "created_at": NOW,
        "updated_at": None,
        "is_silenced": False,
        "silenced_at": None,
        "temp_limit": None,
        "temp_limit_expires_at": None,
        "temp_limit_reason": None,
    }
    for field, default in budget_defaults.items():
        result = await budget_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} budgets")

    # ── 7. Goals ─────────────────────────────────────────────────────
    goal_col = db["goals"]
    count = await goal_col.count_documents({})
    logger.info(f"Goals collection: {count} documents")

    goal_defaults = {
        "currency": "VND",
        "current_amount": 0.0,
        "deadline": None,
        "category_id": None,
        "status": "active",
        "created_at": NOW,
    }
    for field, default in goal_defaults.items():
        result = await goal_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} goals")

    # ── 8. Subscriptions ─────────────────────────────────────────────
    sub_col = db["subscriptions"]
    count = await sub_col.count_documents({})
    logger.info(f"Subscriptions collection: {count} documents")

    sub_defaults = {
        "currency": "VND",
        "period": "monthly",
        "last_charged_at": None,
        "is_active": True,
        "source": "manual",
        "created_at": NOW,
        "cancelled_at": None,
        "cancellation_reason": None,
        "replaces_id": None,
    }
    for field, default in sub_defaults.items():
        result = await sub_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} subscriptions")

    # ── 9. Budget Events ─────────────────────────────────────────────
    be_col = db["budget_events"]
    count = await be_col.count_documents({})
    logger.info(f"Budget events collection: {count} documents")

    be_defaults = {
        "old_value": {},
        "new_value": {},
        "reason": None,
        "triggered_by": "user",
        "created_at": NOW,
    }
    for field, default in be_defaults.items():
        result = await be_col.update_many(
            {field: {"$exists": False}},
            {"$set": {field: default}},
        )
        if result.modified_count:
            logger.info(f"  Set default {field} for {result.modified_count} budget events")

    # ── Done ─────────────────────────────────────────────────────────
    logger.info("Migration completed successfully!")
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate())
