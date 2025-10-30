"""Workflow routes for managing user workflows."""

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from middleware.auth import require_auth
from services.workflow_service import (
    create_workflow,
    get_user_workflows,
    get_workflow_by_id,
    update_workflow,
    delete_workflow,
    archive_workflow,
    get_workflow_count
)

router = APIRouter()


class CreateWorkflowRequest(BaseModel):
    name: str
    steps: List[Dict[str, Any]]
    video_key: Optional[str] = None
    description: Optional[str] = None
    n8n_workflow_id: Optional[str] = None
    n8n_workflow_data: Optional[Dict[str, Any]] = None


class UpdateWorkflowRequest(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    status: Optional[str] = None
    n8n_workflow_id: Optional[str] = None
    n8n_workflow_data: Optional[Dict[str, Any]] = None


@router.post("/")
async def create_user_workflow(
    request: CreateWorkflowRequest,
    user: Dict = Depends(require_auth)
):
    """Create a new workflow for the authenticated user."""
    try:
        user_id = user["user_id"]

        workflow = create_workflow(
            user_id=user_id,
            name=request.name,
            steps=request.steps,
            video_key=request.video_key,
            description=request.description,
            n8n_workflow_id=request.n8n_workflow_id,
            n8n_workflow_data=request.n8n_workflow_data
        )

        return {
            "success": True,
            "workflow": workflow
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_workflows(
    user: Dict = Depends(require_auth),
    status: Optional[str] = Query(None, description="Filter by status: active, draft, archived"),
    limit: int = Query(100, ge=1, le=1000, description="Maximum number of workflows to return"),
    offset: int = Query(0, ge=0, description="Number of workflows to skip")
):
    """Get all workflows for the authenticated user."""
    try:
        user_id = user["user_id"]

        workflows = get_user_workflows(
            user_id=user_id,
            status=status,
            limit=limit,
            offset=offset
        )

        total_count = get_workflow_count(user_id, status)

        return {
            "workflows": workflows,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}")
async def get_workflow(
    workflow_id: str,
    user: Dict = Depends(require_auth)
):
    """Get a specific workflow by ID."""
    try:
        user_id = user["user_id"]

        workflow = get_workflow_by_id(workflow_id, user_id)

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        return {
            "workflow": workflow
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{workflow_id}")
async def update_user_workflow(
    workflow_id: str,
    request: UpdateWorkflowRequest,
    user: Dict = Depends(require_auth)
):
    """Update a workflow."""
    try:
        user_id = user["user_id"]

        # Only include fields that were provided
        updates = {}
        if request.name is not None:
            updates["name"] = request.name
        if request.description is not None:
            updates["description"] = request.description
        if request.steps is not None:
            updates["steps"] = request.steps
        if request.status is not None:
            updates["status"] = request.status
        if request.n8n_workflow_id is not None:
            updates["n8n_workflow_id"] = request.n8n_workflow_id
        if request.n8n_workflow_data is not None:
            updates["n8n_workflow_data"] = request.n8n_workflow_data

        if not updates:
            raise HTTPException(status_code=400, detail="No fields to update")

        workflow = update_workflow(workflow_id, user_id, updates)

        return {
            "success": True,
            "workflow": workflow
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{workflow_id}")
async def delete_user_workflow(
    workflow_id: str,
    user: Dict = Depends(require_auth)
):
    """Delete a workflow."""
    try:
        user_id = user["user_id"]

        delete_workflow(workflow_id, user_id)

        return {
            "success": True,
            "message": "Workflow deleted successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{workflow_id}/archive")
async def archive_user_workflow(
    workflow_id: str,
    user: Dict = Depends(require_auth)
):
    """Archive a workflow (soft delete)."""
    try:
        user_id = user["user_id"]

        workflow = archive_workflow(workflow_id, user_id)

        return {
            "success": True,
            "workflow": workflow,
            "message": "Workflow archived successfully"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/stats/summary")
async def get_workflow_stats(user: Dict = Depends(require_auth)):
    """Get workflow statistics for the user."""
    try:
        user_id = user["user_id"]

        total = get_workflow_count(user_id)
        active = get_workflow_count(user_id, "active")
        draft = get_workflow_count(user_id, "draft")
        archived = get_workflow_count(user_id, "archived")

        return {
            "total": total,
            "active": active,
            "draft": draft,
            "archived": archived
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
