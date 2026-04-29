from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

# Patch category_names globally for tests to avoid early Beanie initialization during imports
patch("src.core.categories.category_names", return_value=["Khác", "Ăn uống", "Di chuyển"]).start()
patch("src.core.categories.load_categories", return_value=[]).start()

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from src.db.models.user import UserDocument, UserProfileDocument
from src.db.models.transaction import TransactionDocument
from src.db.models.budget import BudgetDocument, BudgetEventDocument
from src.db.models.goal import GoalDocument
from src.db.models.nudge import NudgeDocument
from src.db.models.subscription import SubscriptionDocument
from src.db.models.category import CategoryDocument
from src.db.models.correction import CorrectionDocument

# Load .env BEFORE any test module evaluates pytestmark skipif conditions
load_dotenv(Path(__file__).resolve().parent.parent / ".env")


from mongomock_motor import AsyncMongoMockClient

@pytest.fixture(autouse=True)
async def init_test_db():
    """Initialize Beanie with a mock-like database for tests."""
    client = AsyncMongoMockClient()
    db = client.test_db
    
    # Patch to fix compatibility between Beanie and mongomock_motor
    orig_list_collection_names = db.list_collection_names
    async def mocked_list_collection_names(*args, **kwargs):
        kwargs.pop("authorizedCollections", None)
        kwargs.pop("nameOnly", None)
        return await orig_list_collection_names(*args, **kwargs)
    db.list_collection_names = mocked_list_collection_names

    await init_beanie(
        database=db,
        document_models=[
            UserDocument, UserProfileDocument, TransactionDocument,
            BudgetDocument, BudgetEventDocument, GoalDocument,
            NudgeDocument, SubscriptionDocument, CategoryDocument,
            CorrectionDocument
        ]
    )


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
    client.delete_merchant_cache = AsyncMock(return_value=None)
    client.get_session = AsyncMock(return_value=None)
    client.set_session = AsyncMock(return_value=None)
    client.set_last_transaction = AsyncMock(return_value=None)
    client.get_last_transaction = AsyncMock(return_value=None)
    client.invalidate_dashboard_cache = AsyncMock(return_value=None)
    return client


@pytest.fixture
def mock_transaction_repo():
    """Mock TransactionRepository."""
    repo = MagicMock()
    repo.insert = AsyncMock(return_value="mock_txn_id_123")
    repo.find_by_id = AsyncMock(return_value=None)
    repo.find_by_user = AsyncMock(return_value=[])
    repo.find_by_merchant = AsyncMock(return_value=[])
    repo.update_category = AsyncMock(return_value=True)
    repo.delete = AsyncMock(return_value=True)
    repo.lock = AsyncMock(return_value=True)
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

@pytest.fixture
def mock_user_repo():
    """Mock UserRepository."""
    from unittest.mock import AsyncMock, MagicMock
    repo = MagicMock()
    repo.find_by_id = AsyncMock(return_value=None)
    repo.get_profile = AsyncMock(return_value=MagicMock())
    return repo
