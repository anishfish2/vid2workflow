"""Authentication service for managing users and JWT tokens."""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")  # Use service key for admin operations
)

# JWT configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRATION_MINUTES = int(os.getenv("JWT_EXPIRATION_MINUTES", "1440"))


def create_jwt_token(user_id: str, email: str) -> str:
    """Create a JWT token for a user."""
    expiration = datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)

    payload = {
        "sub": user_id,  # subject (user_id)
        "email": email,
        "exp": expiration,
        "iat": datetime.utcnow()
    }

    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token


def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError as e:
        raise ValueError(f"Invalid token: {str(e)}")


def get_or_create_user(email: str, name: Optional[str] = None, avatar_url: Optional[str] = None) -> Dict[str, Any]:
    """Get existing user or create new one."""
    try:
        # Try to get existing user
        response = supabase.table("users").select("*").eq("email", email).execute()

        if response.data and len(response.data) > 0:
            # User exists, update if name or avatar changed
            user = response.data[0]
            updates = {}

            if name and user.get("name") != name:
                updates["name"] = name
            if avatar_url and user.get("avatar_url") != avatar_url:
                updates["avatar_url"] = avatar_url

            if updates:
                updates["updated_at"] = datetime.utcnow().isoformat()
                response = supabase.table("users").update(updates).eq("id", user["id"]).execute()
                return response.data[0]

            return user
        else:
            # Create new user
            new_user = {
                "email": email,
                "name": name,
                "avatar_url": avatar_url
            }
            response = supabase.table("users").insert(new_user).execute()
            return response.data[0]

    except Exception as e:
        raise Exception(f"Error managing user: {str(e)}")


def get_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    try:
        response = supabase.table("users").select("*").eq("id", user_id).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    except Exception as e:
        raise Exception(f"Error fetching user: {str(e)}")


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email."""
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    except Exception as e:
        raise Exception(f"Error fetching user: {str(e)}")


def delete_user(user_id: str) -> bool:
    """Delete a user (cascades to oauth_tokens)."""
    try:
        supabase.table("users").delete().eq("id", user_id).execute()
        return True

    except Exception as e:
        raise Exception(f"Error deleting user: {str(e)}")
