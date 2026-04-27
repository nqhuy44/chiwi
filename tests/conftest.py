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
    repo.find_by_merchant = AsyncMock(return_value=[])
    repo.update_category = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_telegram():
    """Mock TelegramService."""
    svc = MagicMock()
    svc.send_message = AsyncMock(return_value=None)
    svc.send_message_with_keyboard = AsyncMock(return_value=None)
    svc.edit_message_reply_markup = AsyncMock(return_value=None)
    svc.answer_callback_query = AsyncMock(return_value=None)
    return svc


@pytest.fixture
def mock_budget_repo():
    """Mock BudgetRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_budget_id")
    repo.find_by_user = AsyncMock(return_value=[])
    repo.find_by_category = AsyncMock(return_value=None)
    repo.update = AsyncMock(return_value=True)
    repo.clear_temp_override = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_budget_event_repo():
    """Mock BudgetEventRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_budget_event_id")
    return repo


@pytest.fixture
def mock_goal_repo():
    """Mock GoalRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_goal_id")
    repo.find_by_user = AsyncMock(return_value=[])
    repo.update_progress = AsyncMock(return_value=True)
    return repo


@pytest.fixture
def mock_correction_repo():
    """Mock CorrectionRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_correction_id")
    return repo


@pytest.fixture
def mock_nudge_repo():
    """Mock NudgeRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_nudge_id")
    repo.find_recent = AsyncMock(return_value=[])
    repo.count_today = AsyncMock(return_value=0)
    return repo


@pytest.fixture
def mock_subscription_repo():
    """Mock SubscriptionRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_sub_id")
    repo.find_by_user = AsyncMock(return_value=[])
    repo.find_by_merchant = AsyncMock(return_value=[])
    repo.find_upcoming = AsyncMock(return_value=[])
    repo.deactivate = AsyncMock(return_value=True)
    return repo
