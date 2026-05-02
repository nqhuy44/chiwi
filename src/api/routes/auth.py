import logging
import random
from datetime import timedelta, UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from src.core.config import settings
from src.core.dependencies import container
from src.core.security import (create_access_token, create_refresh_token,
                               get_password_hash, verify_password)
from src.core.schemas import (
    RegisterRequest, LoginRequest, TokenResponse, 
    ForgotPasswordRequest, ResetPasswordRequest
)
from src.db.models.user import UserDocument, UserProfileDocument

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["Auth"])


import uuid
from src.db.models.user import UserDocument, UserProfileDocument

@router.post("/register", response_model=TokenResponse)
async def register(body: RegisterRequest):
    """Create a new user identity and default profile."""
    user_repo = container.user_repo
    
    # Check if username exists
    existing_username = await user_repo.find_by_username(body.username)
    if existing_username:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered"
        )
    
    # Check if email exists
    if body.email:
        existing_email = await user_repo.find_by_email(body.email)
        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
    
    # Generate unique internal ID (retry if somehow exists)
    user_id = str(uuid.uuid4())
    for _ in range(3): # Safety retry
        if not await user_repo.find_by_id(user_id):
            break
        user_id = str(uuid.uuid4())
    
    # Create User
    hashed_pwd = get_password_hash(body.password)
    user_doc = UserDocument(
        user_id=user_id,
        username=body.username,
        hashed_password=hashed_pwd,
        email=body.email
    )
    await user_repo.create_user(user_doc)
    
    # Create Default Profile
    # Use full_name if provided, else username as initial display_name
    display_name = body.full_name or body.username
    profile_doc = UserProfileDocument(
        user_id=user_id,
        display_name=display_name,
        timezone="Asia/Ho_Chi_Minh",
        language="vi"
    )
    await user_repo.update_profile(user_id, profile_doc)
    
    logger.info("New user registered: %s (id=%s)", body.username, user_id)
    
    # Issue Tokens - use user_id (UUID) as the 'sub'
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user_id=user_id
    )


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest):
    """Authenticate and return JWT tokens."""
    user_repo = container.user_repo
    # Find by username
    user = await user_repo.find_by_username(body.username)
    
    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    user_id = user.user_id
    access_token = create_access_token(data={"sub": user_id})
    refresh_token = create_refresh_token(data={"sub": user_id})
    
    logger.info("User logged in: %s (id=%s)", body.username, user_id)
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


@router.post("/request-reset")
async def request_password_reset(body: ForgotPasswordRequest):
    """Generate and send a password reset code to the user's email."""
    user_repo = container.user_repo
    user = await user_repo.find_by_email(body.email)
    if not user:
        # Prevent email enumeration by always returning success
        return {"message": "If that email is registered, a reset code has been sent."}
    
    # Generate 6-digit code
    code = f"{random.randint(0, 999999):06d}"
    expires_at = datetime.now(UTC) + timedelta(minutes=15)
    
    await user_repo.set_reset_code(body.email, code, expires_at)
    
    # Mock sending email
    logger.info("MOCK EMAIL: Password reset code for %s is %s", body.email, code)
    
    return {"message": "If that email is registered, a reset code has been sent."}


@router.post("/confirm-reset")
async def confirm_password_reset(body: ResetPasswordRequest):
    """Verify the reset code and update the password."""
    user_repo = container.user_repo
    
    user = await user_repo.verify_reset_code(body.email, body.code)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code"
        )
    
    hashed_password = get_password_hash(body.new_password)
    success = await user_repo.update_password_by_email(body.email, hashed_password)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update password"
        )
        
    logger.info("Password reset successful for user: %s", body.email)
    return {"message": "Password has been successfully reset."}
