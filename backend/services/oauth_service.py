"""OAuth service for managing Google OAuth tokens."""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from cryptography.fernet import Fernet
import base64
from supabase import create_client, Client
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from dotenv import load_dotenv

load_dotenv()

# Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)

# Encryption setup
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY")
# Ensure key is properly formatted for Fernet (32 bytes, base64 encoded)
if ENCRYPTION_KEY:
    # If the key isn't already base64 encoded, encode it
    try:
        encryption_key_bytes = ENCRYPTION_KEY.encode()
        if len(encryption_key_bytes) < 32:
            # Pad to 32 bytes
            encryption_key_bytes = encryption_key_bytes + b'=' * (32 - len(encryption_key_bytes))
        fernet_key = base64.urlsafe_b64encode(encryption_key_bytes[:32])
        cipher = Fernet(fernet_key)
    except Exception:
        raise ValueError("ENCRYPTION_KEY must be set in environment variables")
else:
    raise ValueError("ENCRYPTION_KEY not found in environment")

# Google OAuth configuration
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

GOOGLE_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.modify',
]


def encrypt_token(token: str) -> str:
    """Encrypt a token for storage."""
    return cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a stored token."""
    return cipher.decrypt(encrypted_token.encode()).decode()


def create_oauth_flow(state: Optional[str] = None) -> Flow:
    """Create a Google OAuth flow."""
    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": GOOGLE_CLIENT_ID,
                "client_secret": GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [GOOGLE_REDIRECT_URI]
            }
        },
        scopes=GOOGLE_SCOPES,
        redirect_uri=GOOGLE_REDIRECT_URI
    )

    if state:
        flow.state = state

    return flow


def get_authorization_url() -> tuple[str, str]:
    """Get the Google OAuth authorization URL."""
    flow = create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'  # Force consent to ensure we get refresh token
    )
    return authorization_url, state


def exchange_code_for_tokens(code: str, state: str) -> Dict[str, Any]:
    """Exchange authorization code for access and refresh tokens."""
    flow = create_oauth_flow(state=state)
    flow.fetch_token(code=code)

    credentials = flow.credentials

    return {
        "access_token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": credentials.token_uri,
        "client_id": credentials.client_id,
        "client_secret": credentials.client_secret,
        "scopes": credentials.scopes,
        "expiry": credentials.expiry.isoformat() if credentials.expiry else None
    }


def store_oauth_tokens(user_id: str, tokens: Dict[str, Any]) -> None:
    """Store OAuth tokens in database (encrypted)."""
    try:
        # Encrypt sensitive tokens
        encrypted_access_token = encrypt_token(tokens["access_token"])
        encrypted_refresh_token = encrypt_token(tokens["refresh_token"]) if tokens.get("refresh_token") else None

        # Calculate expiry time
        expiry = tokens.get("expiry")
        if expiry:
            expires_at = expiry
        else:
            # Default to 1 hour from now if not provided
            expires_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()

        token_data = {
            "user_id": user_id,
            "provider": "google",
            "access_token": encrypted_access_token,
            "refresh_token": encrypted_refresh_token,
            "token_type": "Bearer",
            "expires_at": expires_at,
            "scopes": tokens.get("scopes", GOOGLE_SCOPES)
        }

        # Upsert (insert or update if exists)
        response = supabase.table("oauth_tokens").upsert(
            token_data,
            on_conflict="user_id,provider"
        ).execute()

        print(f"Stored OAuth tokens for user {user_id}")

    except Exception as e:
        raise Exception(f"Error storing OAuth tokens: {str(e)}")


def get_oauth_tokens(user_id: str, provider: str = "google") -> Optional[Dict[str, Any]]:
    """Retrieve OAuth tokens from database (decrypted)."""
    try:
        response = supabase.table("oauth_tokens").select("*").eq(
            "user_id", user_id
        ).eq("provider", provider).execute()

        if not response.data or len(response.data) == 0:
            return None

        token_data = response.data[0]

        # Decrypt tokens
        decrypted_data = {
            "access_token": decrypt_token(token_data["access_token"]),
            "refresh_token": decrypt_token(token_data["refresh_token"]) if token_data.get("refresh_token") else None,
            "token_type": token_data.get("token_type", "Bearer"),
            "expires_at": token_data.get("expires_at"),
            "scopes": token_data.get("scopes", [])
        }

        return decrypted_data

    except Exception as e:
        raise Exception(f"Error retrieving OAuth tokens: {str(e)}")


def refresh_access_token(user_id: str) -> Optional[str]:
    """Refresh the access token using the refresh token."""
    try:
        tokens = get_oauth_tokens(user_id)

        if not tokens or not tokens.get("refresh_token"):
            print(f"No refresh token found for user {user_id}")
            return None

        # Create credentials with refresh token
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens["refresh_token"],
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=tokens.get("scopes", GOOGLE_SCOPES)
        )

        # Refresh the token
        request = Request()
        credentials.refresh(request)

        # Store updated tokens
        updated_tokens = {
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token or tokens["refresh_token"],  # Keep old if not provided
            "expiry": credentials.expiry.isoformat() if credentials.expiry else None,
            "scopes": credentials.scopes
        }

        store_oauth_tokens(user_id, updated_tokens)

        print(f"Refreshed access token for user {user_id}")
        return credentials.token

    except Exception as e:
        print(f"Error refreshing token for user {user_id}: {str(e)}")
        return None


def get_valid_credentials(user_id: str) -> Optional[Credentials]:
    """Get valid Google credentials, refreshing if necessary."""
    try:
        tokens = get_oauth_tokens(user_id)

        if not tokens:
            return None

        # Create credentials
        credentials = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=tokens.get("scopes", GOOGLE_SCOPES)
        )

        # Check if token is expired or about to expire (within 5 minutes)
        if tokens.get("expires_at"):
            from datetime import timezone
            expires_at = datetime.fromisoformat(tokens["expires_at"].replace('Z', '+00:00'))
            now_utc = datetime.now(timezone.utc)
            if now_utc >= expires_at - timedelta(minutes=5):
                print(f"Token expired or expiring soon, refreshing for user {user_id}")
                refresh_access_token(user_id)
                # Get fresh tokens
                tokens = get_oauth_tokens(user_id)
                if tokens:
                    credentials = Credentials(
                        token=tokens["access_token"],
                        refresh_token=tokens.get("refresh_token"),
                        token_uri="https://oauth2.googleapis.com/token",
                        client_id=GOOGLE_CLIENT_ID,
                        client_secret=GOOGLE_CLIENT_SECRET,
                        scopes=tokens.get("scopes", GOOGLE_SCOPES)
                    )

        return credentials

    except Exception as e:
        print(f"Error getting valid credentials for user {user_id}: {str(e)}")
        return None


def delete_oauth_tokens(user_id: str, provider: str = "google") -> bool:
    """Delete OAuth tokens for a user."""
    try:
        supabase.table("oauth_tokens").delete().eq("user_id", user_id).eq("provider", provider).execute()
        print(f"Deleted OAuth tokens for user {user_id}")
        return True

    except Exception as e:
        print(f"Error deleting OAuth tokens: {str(e)}")
        return False
