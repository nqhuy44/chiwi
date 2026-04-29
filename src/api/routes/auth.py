import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.core.config import settings
from src.core.dependencies import container
from src.core.security import (create_access_token, create_refresh_token,
                               get_password_hash, verify_password)
from src.core.schemas import RegisterRequest, LoginRequest, TokenResponse
from src.db.models.user import UserDocument, UserProfileDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest):
    """Create a new user identity and default profile."""
    user_repo = container.user_repo
    
    # Check if exists
    existing = await user_repo.find_by_id(body.username)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Create User
    hashed_pwd = get_password_hash(body.password)
    user_doc = UserDocument(
        user_id=body.username,  # Use username as id for mobile-first simplicity
        username=body.username,
        hashed_password=hashed_pwd,
        full_name=body.full_name
    )
    await user_repo.create_user(user_doc)
    
    # Create Default Profile
    profile_doc = UserProfileDocument(
        user_id=body.username,
        timezone="Asia/Ho_Chi_Minh",
        language="vi"
    )
    await user_repo.update_profile(body.username, profile_doc)
    
    logger.info("New user registered: %s", body.username)
    
    # Issue Tokens
    access_token = create_access_token(data={"sub": body.username})
    refresh_token = create_refresh_token(data={"sub": body.username})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=body.username
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate and return JWT tokens."""
    user_repo = container.user_repo
    user = await user_repo.find_by_id(body.username)
    
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = user.user_id
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    # Optionally store refresh token hash in DB for invalidation
    # await user_repo.update_user(user_id, {"refresh_token_hash": ...})
    
    logger.info("User logged in: %s", user_id)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(refresh_token: str):
    """Issue a new access token using a refresh token."""
    from src.core.security import decode_token
    try:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
            
        new_access = create_access_token(data={"sub": user_id})
        # Keep same refresh token or rotate
        return TokenResponse(
            access_token=new_access,
            refresh_token=refresh_token,
            user_id=user_id
        )
    except Exception:
        raise HTTPException(status_code=401, detail="Could not validate refresh token")
