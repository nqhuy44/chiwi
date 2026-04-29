"""Unit tests for UserRepository data privacy logic."""

import pytest
from src.db.repositories.user_repo import UserRepository
from src.db.models.user import UserDocument, UserProfileDocument
from src.db.models.transaction import TransactionDocument

@pytest.mark.asyncio
async def test_delete_user_data_integration():
    """Verify that delete_user_data actually removes documents from the DB."""
    repo = UserRepository()
    user_id = "user_123"
    
    # Create some dummy data
    user = UserDocument(user_id=user_id, username="testuser", telegram_chat_id="123")
    await user.insert()
    
    from datetime import datetime, UTC
    txn = TransactionDocument(
        user_id=user_id, 
        amount=100.0, 
        direction="outflow", 
        raw_text="test",
        source="manual",
        transaction_time=datetime.now(UTC)
    )
    await txn.insert()
    
    # Verify they exist
    assert await UserDocument.find_one(UserDocument.user_id == user_id) is not None
    assert await TransactionDocument.find(TransactionDocument.user_id == user_id).count() == 1
    
    # Delete
    await repo.delete_user_data(user_id)
    
    # Verify they are gone
    assert await UserDocument.find_one(UserDocument.user_id == user_id) is None
    assert await TransactionDocument.find(TransactionDocument.user_id == user_id).count() == 0
