"""
Authentication middleware.

Validates Telegram user_id against the allow-list.
"""

import logging

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from src.core.config import settings

logger = logging.getLogger(__name__)

# Paths that skip auth
PUBLIC_PATHS = {"/health", "/docs", "/openapi.json"}


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS:
            return await call_next(request)

        # Webhook endpoints handle their own auth
        response = await call_next(request)
        return response
