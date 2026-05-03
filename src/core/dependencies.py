"""
Application dependency container.

Manages lifecycle of shared services: MongoDB, Redis, Gemini, Telegram.
Injected into FastAPI via lifespan and Depends().
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import settings
from src.db.repositories.budget_repo import BudgetEventRepository, BudgetRepository
from src.db.repositories.correction_repo import CorrectionRepository
from src.db.repositories.goal_repo import GoalRepository
from src.db.repositories.nudge_repo import NudgeRepository
from src.db.repositories.subscription_repo import SubscriptionRepository
from src.db.repositories.transaction_repo import TransactionRepository
from src.db.repositories.user_repo import UserRepository
from src.services.dashboard import DashboardService
from src.services.gemini import GeminiService
from src.services.redis_client import RedisClient
from src.services.telegram import TelegramService

# Lazy import to avoid circular dependency
# from src.core.orchestrator import Orchestrator

logger = logging.getLogger(__name__)


@dataclass
class AppContainer:
    """Holds all shared service instances for the application."""

    mongo_client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None
    redis: RedisClient = field(default_factory=RedisClient)
    gemini: GeminiService = field(default_factory=GeminiService)
    telegram: TelegramService | None = None

    # Repositories (initialized after DB connect)
    transaction_repo: TransactionRepository | None = None
    user_repo: UserRepository | None = None
    budget_repo: BudgetRepository | None = None
    budget_event_repo: BudgetEventRepository | None = None
    goal_repo: GoalRepository | None = None
    correction_repo: CorrectionRepository | None = None
    nudge_repo: NudgeRepository | None = None
    subscription_repo: SubscriptionRepository | None = None

    # Dashboard service (initialized after repos + redis are ready)
    dashboard_service: DashboardService | None = None

    # Agents
    ingestion_agent: Optional["IngestionAgent"] = None
    tagging_agent: Optional["TaggingAgent"] = None

    # Orchestrator (initialized after all services are ready)
    _orchestrator: object | None = None

    async def startup(self) -> None:
        """Connect all services. Called during FastAPI lifespan startup."""
        # MongoDB
        self.mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.mongo_client[settings.mongodb_db_name]
        # Beanie initialization
        from beanie import init_beanie
        from src.db.models.user import UserDocument, UserProfileDocument
        from src.db.models.transaction import TransactionDocument
        from src.db.models.budget import BudgetDocument, BudgetEventDocument
        from src.db.models.category import CategoryDocument
        from src.db.models.correction import CorrectionDocument
        from src.db.models.goal import GoalDocument
        from src.db.models.nudge import NudgeDocument
        from src.db.models.report import ReportDocument
        from src.db.models.subscription import SubscriptionDocument

        await init_beanie(
            database=self.db,
            document_models=[
                UserDocument,
                UserProfileDocument,
                TransactionDocument,
                BudgetDocument,
                BudgetEventDocument,
                CategoryDocument,
                CorrectionDocument,
                GoalDocument,
                NudgeDocument,
                ReportDocument,
                SubscriptionDocument,
            ],
        )
        logger.info("Beanie ODM initialized")

        # Repositories
        self.transaction_repo = TransactionRepository(self.db)
        self.user_repo = UserRepository(self.db)
        self.budget_repo = BudgetRepository(self.db)
        self.budget_event_repo = BudgetEventRepository(self.db)
        self.goal_repo = GoalRepository(self.db)
        self.correction_repo = CorrectionRepository(self.db)
        self.nudge_repo = NudgeRepository(self.db)
        self.subscription_repo = SubscriptionRepository(self.db)

        # Redis
        await self.redis.connect()

        # Gemini
        self.gemini.initialize()

        # Telegram (optional)
        if settings.telegram_enabled:
            self.telegram = TelegramService()
            logger.info("Telegram enabled")
        else:
            logger.info("Telegram disabled (no TELEGRAM_BOT_TOKEN)")

        # Dashboard service
        self.dashboard_service = DashboardService(
            transaction_repo=self.transaction_repo,
            budget_repo=self.budget_repo,
            goal_repo=self.goal_repo,
            subscription_repo=self.subscription_repo,
            nudge_repo=self.nudge_repo,
            redis=self.redis,
        )

        # Agents
        from src.agents.ingestion import IngestionAgent
        from src.agents.tagging import TaggingAgent
        self.ingestion_agent = IngestionAgent(self.gemini)
        self.tagging_agent = TaggingAgent(self.gemini, self.redis, transaction_repo=self.transaction_repo)

        # Orchestrator
        from src.core.orchestrator import Orchestrator

        self._orchestrator = Orchestrator(
            gemini=self.gemini,
            redis=self.redis,
            telegram=self.telegram,
            transaction_repo=self.transaction_repo,
            budget_repo=self.budget_repo,
            budget_event_repo=self.budget_event_repo,
            goal_repo=self.goal_repo,
            correction_repo=self.correction_repo,
            nudge_repo=self.nudge_repo,
            subscription_repo=self.subscription_repo,
        )
        logger.info("All services initialized")

    @property
    def orchestrator(self):
        """Get the shared Orchestrator instance."""
        if self._orchestrator is None:
            raise RuntimeError("Container not started — call startup() first")
        return self._orchestrator

    async def shutdown(self) -> None:
        """Gracefully close all connections."""
        await self.redis.close()

        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB disconnected")

        logger.info("All services shut down")


# Singleton container — populated during lifespan
container = AppContainer()
