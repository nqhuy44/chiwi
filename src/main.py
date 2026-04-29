"""ChiWi — Zero-effort, proactive personal finance via Multi-Agent Swarm."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routes import auth, chat, health, mobile, webhook
from src.core.config import settings
from src.core.dependencies import container

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage startup/shutdown lifecycle for all services."""
    logger.info("ChiWi starting up...")

    if not settings.allowed_user_id_list:
        raise RuntimeError(
            "ALLOWED_USER_IDS is not configured. "
            "Set it to a comma-separated list of authorised user IDs in your .env file. "
            "Example: ALLOWED_USER_IDS=123456789,987654321"
        )

    await container.startup()
    yield
    logger.info("ChiWi shutting down...")
    await container.shutdown()


app = FastAPI(
    title=settings.app_name,
    description="Proactive personal finance management powered by AI agents",
    version="0.1.0",
    lifespan=lifespan,
)

# Routes
app.include_router(health.router)
app.include_router(auth.router)
if settings.telegram_enabled:
    app.include_router(webhook.router)
app.include_router(chat.router)
app.include_router(mobile.router)
