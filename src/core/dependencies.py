"""
Application dependency container.

Manages lifecycle of shared services: MongoDB, Redis, Gemini, Telegram.
Injected into FastAPI via lifespan and Depends().
"""

import logging
from dataclasses import dataclass, field

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.core.config import settings
from src.db.repositories.transaction_repo import TransactionRepository
from src.db.repositories.user_repo import UserRepository
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
    telegram: TelegramService = field(default_factory=TelegramService)

    # Repositories (initialized after DB connect)
    transaction_repo: TransactionRepository | None = None
    user_repo: UserRepository | None = None

    # Orchestrator (initialized after all services are ready)
    _orchestrator: object | None = None

    async def startup(self) -> None:
        """Connect all services. Called during FastAPI lifespan startup."""
        # MongoDB
        self.mongo_client = AsyncIOMotorClient(settings.mongodb_uri)
        self.db = self.mongo_client[settings.mongodb_db_name]
        logger.info(
            "MongoDB connected: %s/%s",
            settings.mongodb_uri,
            settings.mongodb_db_name,
        )

        # Repositories
        self.transaction_repo = TransactionRepository(self.db)
        self.user_repo = UserRepository(self.db)

        # Redis
        await self.redis.connect()

        # Gemini
        self.gemini.initialize()

        # Orchestrator
        from src.core.orchestrator import Orchestrator

        self._orchestrator = Orchestrator(
            gemini=self.gemini,
            redis=self.redis,
            transaction_repo=self.transaction_repo,
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
