"""Shared models for tool API requests and responses."""

from pydantic import BaseModel
from typing import Dict, Any, Optional


class ToolRequest(BaseModel):
    """Standard request format for all tool endpoints."""
    user_id: str
    params: Dict[str, Any]
    session_id: Optional[str] = None


class ToolResponse(BaseModel):
    """Standard response format for all tool endpoints."""
    success: bool
    data: Optional[Any] = None
    error: Optional[str] = None
    retryable: bool = False
