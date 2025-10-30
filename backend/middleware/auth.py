"""Authentication middleware for protecting routes."""

from fastapi import HTTPException, status, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Any
from services.auth_service import decode_jwt_token, get_user_by_id

security = HTTPBearer()


def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict[str, Any]:
    """
    Dependency to get the current authenticated user from JWT token.

    Usage in routes:
        @app.get("/protected")
        def protected_route(current_user: Dict = Depends(get_current_user)):
            user_id = current_user["user_id"]
            email = current_user["email"]
            ...
    """
    try:
        token = credentials.credentials

        # Decode and validate JWT
        payload = decode_jwt_token(token)

        user_id = payload.get("sub")
        email = payload.get("email")

        if not user_id or not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

        # Verify user still exists in database
        user = get_user_by_id(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return {
            "user_id": user_id,
            "email": email,
            "name": user.get("name"),
            "avatar_url": user.get("avatar_url")
        }

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_auth(current_user: Dict = Depends(get_current_user)) -> Dict[str, Any]:
    """
    Simplified dependency that just checks authentication.
    Returns the current user dict.

    Usage:
        @app.get("/protected")
        def protected_route(user: Dict = Depends(require_auth)):
            user_id = user["user_id"]
            ...
    """
    return current_user
