"""Shared pytest fixtures for ChiWi tests."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from dotenv import load_dotenv

# Load .env BEFORE any test module evaluates pytestmark skipif conditions
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


@pytest.fixture
def mock_gemini():
    """Mock GeminiService with AsyncMock for call_flash and call_pro."""
    service = MagicMock()
    service.call_flash = AsyncMock(return_value={})
    service.call_pro = AsyncMock(return_value={})
    return service


@pytest.fixture
def mock_redis():
    """Mock RedisClient with async no-op methods."""
    client = MagicMock()
    client.get_merchant_cache = AsyncMock(return_value=None)
    client.set_merchant_cache = AsyncMock(return_value=None)
    client.get_session = AsyncMock(return_value=None)
    client.set_session = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_transaction_repo():
    """Mock TransactionRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_txn_id_123")
    repo.find_by_user = AsyncMock(return_value=[])
    repo.update_category = AsyncMock(return_value=True)
    return repo
