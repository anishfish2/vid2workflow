"""Video routes for managing uploaded videos."""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from middleware.auth import require_auth
from services.video_service import (
    save_video_record,
    get_user_videos,
    get_video_by_id,
    delete_video,
    get_video_count
)

router = APIRouter()


class SaveVideoRequest(BaseModel):
    s3_key: str
    filename: str
    file_size: Optional[int] = None
    duration: Optional[float] = None


@router.post("/")
async def save_video(
    request: SaveVideoRequest,
    user: Dict = Depends(require_auth)
):
    """Save a video record after upload."""
    try:
        user_id = user["user_id"]

        video = save_video_record(
            user_id=user_id,
            s3_key=request.s3_key,
            filename=request.filename,
            file_size=request.file_size,
            duration=request.duration
        )

        return {
            "success": True,
            "video": video
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_videos(
    user: Dict = Depends(require_auth),
    limit: int = 100,
    offset: int = 0
):
    """Get all videos for the authenticated user."""
    try:
        user_id = user["user_id"]

        videos = get_user_videos(
            user_id=user_id,
            limit=limit,
            offset=offset
        )

        total_count = get_video_count(user_id)

        return {
            "videos": videos,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{video_id}")
async def get_video(
    video_id: str,
    user: Dict = Depends(require_auth)
):
    """Get a specific video by ID."""
    try:
        user_id = user["user_id"]

        video = get_video_by_id(video_id, user_id)

        if not video:
            raise HTTPException(status_code=404, detail="Video not found")

        return {
            "video": video
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{video_id}")
async def delete_user_video(
    video_id: str,
    user: Dict = Depends(require_auth)
):
    """Delete a video record."""
    try:
        user_id = user["user_id"]

        delete_video(video_id, user_id)

        return {
            "success": True,
            "message": "Video deleted successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
