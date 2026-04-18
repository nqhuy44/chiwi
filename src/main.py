"""ChiWi — Zero-effort, proactive personal finance via Multi-Agent Swarm."""

import logging

from fastapi import FastAPI

from src.api.routes import chat, health, webhook
from src.core.config import settings

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s",
)

app = FastAPI(
    title=settings.app_name,
    description="Proactive personal finance management powered by AI agents",
    version="0.1.0",
)

# Routes
app.include_router(health.router)
app.include_router(webhook.router)
app.include_router(chat.router)


@app.on_event("startup")
async def startup():
    logging.getLogger(__name__).info("ChiWi starting up...")
    # TODO: Connect MongoDB, Redis, register Telegram webhook


@app.on_event("shutdown")
async def shutdown():
    logging.getLogger(__name__).info("ChiWi shutting down...")
    # TODO: Close connections
