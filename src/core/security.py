import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext
from src.core.config import settings

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

ALGORITHM = "HS256"

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check if plain password matches hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generate bcrypt hash."""
    return pwd_context.hash(password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    """Generate JWT Access Token."""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(minutes=settings.jwt_access_token_expire_minutes)
    
    to_encode.update({"exp": expire, "type": "access"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def create_refresh_token(data: dict) -> str:
    """Generate JWT Refresh Token (longer lived)."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + timedelta(days=settings.jwt_refresh_token_expire_days)
    to_encode.update({"exp": expire, "type": "refresh"})
    encoded_jwt = jwt.encode(to_encode, settings.jwt_secret_key, algorithm=ALGORITHM)
    return encoded_jwt

def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT."""
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        logger.warning("Token expired")
        raise
    except jwt.InvalidTokenError:
        logger.warning("Invalid token")
        raise
