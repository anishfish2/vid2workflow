"""Authentication routes for OAuth and session management."""

from fastapi import APIRouter, HTTPException, Query, Depends, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from typing import Optional, Dict, Any
from services.auth_service import create_jwt_token, get_or_create_user, get_user_by_id
from services.oauth_service import (
    get_authorization_url,
    exchange_code_for_tokens,
    store_oauth_tokens,
    delete_oauth_tokens,
    get_oauth_tokens
)
from middleware.auth import require_auth
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import os

router = APIRouter()

# Store OAuth state temporarily (in production, use Redis)
oauth_states = {}


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


@router.get("/google/login")
async def google_login():
    """Initiate Google OAuth flow."""
    try:
        authorization_url, state = get_authorization_url()

        # Store state for verification (in production, use Redis with expiry)
        oauth_states[state] = True

        # Redirect user to Google OAuth consent screen
        return RedirectResponse(url=authorization_url)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth initialization failed: {str(e)}")


@router.get("/google/callback")
async def google_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from OAuth provider")
):
    """Handle Google OAuth callback."""
    try:
        # Check for OAuth errors
        if error:
            raise HTTPException(status_code=400, detail=f"OAuth error: {error}")

        # Verify state (CSRF protection)
        if state not in oauth_states:
            raise HTTPException(status_code=400, detail="Invalid state parameter")

        # Remove used state
        del oauth_states[state]

        # Exchange authorization code for tokens
        tokens = exchange_code_for_tokens(code, state)

        # Get user info from Google
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_uri=tokens.get("token_uri"),
            client_id=tokens.get("client_id"),
            client_secret=tokens.get("client_secret"),
            scopes=tokens.get("scopes")
        )

        # Get user profile from Google
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()

        email = user_info.get('email')
        name = user_info.get('name')
        avatar_url = user_info.get('picture')

        if not email:
            raise HTTPException(status_code=400, detail="Email not provided by Google")

        # Get or create user in database
        user = get_or_create_user(email, name, avatar_url)
        user_id = user['id']

        # Store OAuth tokens
        store_oauth_tokens(user_id, tokens)

        # Create JWT for session
        jwt_token = create_jwt_token(user_id, email)

        # Get frontend URL from environment
        frontend_url = os.getenv("FRONTEND_URL", "http://localhost:3000")

        # Redirect to frontend with token in URL (frontend will store it)
        return RedirectResponse(
            url=f"{frontend_url}/auth/callback?token={jwt_token}"
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication failed: {str(e)}")


@router.post("/logout")
async def logout(user: Dict = Depends(require_auth)):
    """Logout user and optionally revoke OAuth tokens."""
    try:
        user_id = user["user_id"]

        # Delete OAuth tokens from database
        delete_oauth_tokens(user_id)

        return {
            "success": True,
            "message": "Logged out successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")


@router.get("/me")
async def get_current_user_info(user: Dict = Depends(require_auth)):
    """Get current authenticated user information."""
    try:
        user_id = user["user_id"]

        # Get full user data
        user_data = get_user_by_id(user_id)

        if not user_data:
            raise HTTPException(status_code=404, detail="User not found")

        # Check if user has Google OAuth connected
        has_google_auth = get_oauth_tokens(user_id) is not None

        return {
            "id": user_data["id"],
            "email": user_data["email"],
            "name": user_data.get("name"),
            "avatar_url": user_data.get("avatar_url"),
            "created_at": user_data.get("created_at"),
            "has_google_auth": has_google_auth
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching user info: {str(e)}")


@router.get("/status")
async def auth_status(user: Dict = Depends(require_auth)):
    """Check authentication status."""
    return {
        "authenticated": True,
        "user_id": user["user_id"],
        "email": user["email"]
    }


@router.post("/refresh")
async def refresh_token(user: Dict = Depends(require_auth)):
    """Refresh JWT token."""
    try:
        user_id = user["user_id"]
        email = user["email"]

        # Create new JWT token
        new_token = create_jwt_token(user_id, email)

        return {
            "access_token": new_token,
            "token_type": "bearer"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Token refresh failed: {str(e)}")
