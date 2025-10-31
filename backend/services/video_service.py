"""Video service for managing uploaded videos."""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

# Supabase client
supabase: Client = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_SERVICE_KEY")
)


def save_video_record(
    user_id: str,
    s3_key: str,
    filename: str,
    file_size: Optional[int] = None,
    duration: Optional[float] = None
) -> Dict[str, Any]:
    """Save a record of an uploaded video."""
    try:
        video_data = {
            "user_id": user_id,
            "s3_key": s3_key,
            "filename": filename,
            "file_size": file_size,
            "duration": duration,
            "uploaded_at": datetime.utcnow().isoformat()
        }

        response = supabase.table("videos").insert(video_data).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            raise Exception("Failed to save video record")

    except Exception as e:
        raise Exception(f"Error saving video record: {str(e)}")


def get_user_videos(
    user_id: str,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get all videos for a user."""
    try:
        query = supabase.table("videos").select("*").eq("user_id", user_id)
        query = query.order("uploaded_at", desc=True).limit(limit).offset(offset)

        response = query.execute()

        return response.data if response.data else []

    except Exception as e:
        raise Exception(f"Error fetching videos: {str(e)}")


def get_video_by_id(video_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific video by ID."""
    try:
        response = supabase.table("videos").select("*").eq(
            "id", video_id
        ).eq("user_id", user_id).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    except Exception as e:
        raise Exception(f"Error fetching video: {str(e)}")


def get_video_by_s3_key(s3_key: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a video by its S3 key."""
    try:
        response = supabase.table("videos").select("*").eq(
            "s3_key", s3_key
        ).eq("user_id", user_id).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    except Exception as e:
        raise Exception(f"Error fetching video by S3 key: {str(e)}")


def delete_video(video_id: str, user_id: str) -> bool:
    """Delete a video record."""
    try:
        # Verify ownership
        video = get_video_by_id(video_id, user_id)
        if not video:
            raise Exception("Video not found or access denied")

        supabase.table("videos").delete().eq(
            "id", video_id
        ).eq("user_id", user_id).execute()

        return True

    except Exception as e:
        raise Exception(f"Error deleting video: {str(e)}")


def get_video_count(user_id: str) -> int:
    """Get count of videos for a user."""
    try:
        query = supabase.table("videos").select("id", count="exact").eq("user_id", user_id)
        response = query.execute()

        return response.count if hasattr(response, 'count') else 0

    except Exception as e:
        raise Exception(f"Error counting videos: {str(e)}")
