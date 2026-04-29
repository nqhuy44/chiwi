import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.core.security import decode_token
from src.core.dependencies import container

logger = logging.getLogger(__name__)
security = HTTPBearer()

async def get_current_user(auth: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Dependency to validate JWT and return the user_id."""
    token = auth.credentials
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
        
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing subject"
            )
            
        # Optional: Verify user still exists in DB
        # user = await container.user_repo.find_by_id(user_id)
        # if not user:
        #     raise HTTPException(status_code=401, detail="User not found")
            
        return user_id
    except Exception as e:
        logger.warning("Auth failure: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
