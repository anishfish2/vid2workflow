"""Workflow service for managing user workflows."""

import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL") or "http://localhost:54321"
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or "your-service-key"

supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)


def create_workflow(
    user_id: str,
    name: str,
    steps: List[Dict[str, Any]],
    video_key: Optional[str] = None,
    description: Optional[str] = None,
    n8n_workflow_id: Optional[str] = None,
    n8n_workflow_data: Optional[Dict[str, Any]] = None,
    status: str = "active",
    missing_info: Optional[List[Dict[str, Any]]] = None,
    collected_params: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Create a new workflow for a user."""
    try:
        workflow_data = {
            "user_id": user_id,
            "name": name,
            "description": description,
            "video_key": video_key,
            "steps": steps,
            "n8n_workflow_id": n8n_workflow_id,
            "n8n_workflow_data": n8n_workflow_data,
            "status": status,
            "missing_info": missing_info if missing_info is not None else [],
            "collected_params": collected_params if collected_params is not None else {},
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }

        print(f"[workflow_service] Inserting workflow with steps type: {type(steps)}")
        if isinstance(steps, list) and len(steps) > 0:
            print(f"[workflow_service] First step: {steps[0]}")

        response = supabase.table("workflows").insert(workflow_data).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            raise Exception("Failed to create workflow")

    except Exception as e:
        raise Exception(f"Error creating workflow: {str(e)}")


def get_user_workflows(
    user_id: str,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Get all workflows for a user."""
    try:
        query = supabase.table("workflows").select("*").eq("user_id", user_id)

        if status:
            query = query.eq("status", status)

        query = query.order("created_at", desc=True).limit(limit).offset(offset)

        response = query.execute()

        return response.data if response.data else []

    except Exception as e:
        raise Exception(f"Error fetching workflows: {str(e)}")


def get_workflow_by_id(workflow_id: str, user_id: str) -> Optional[Dict[str, Any]]:
    """Get a specific workflow by ID (with user verification)."""
    try:
        response = supabase.table("workflows").select("*").eq(
            "id", workflow_id
        ).eq("user_id", user_id).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        return None

    except Exception as e:
        raise Exception(f"Error fetching workflow: {str(e)}")


def update_workflow(
    workflow_id: str,
    user_id: str,
    updates: Dict[str, Any]
) -> Dict[str, Any]:
    """Update a workflow."""
    try:
        # Verify ownership
        workflow = get_workflow_by_id(workflow_id, user_id)
        if not workflow:
            raise Exception("Workflow not found or access denied")

        # Add updated timestamp
        updates["updated_at"] = datetime.utcnow().isoformat()

        response = supabase.table("workflows").update(updates).eq(
            "id", workflow_id
        ).eq("user_id", user_id).execute()

        if response.data and len(response.data) > 0:
            return response.data[0]
        else:
            raise Exception("Failed to update workflow")

    except Exception as e:
        raise Exception(f"Error updating workflow: {str(e)}")


def delete_workflow(workflow_id: str, user_id: str) -> bool:
    """Delete a workflow."""
    try:
        # Verify ownership
        workflow = get_workflow_by_id(workflow_id, user_id)
        if not workflow:
            raise Exception("Workflow not found or access denied")

        supabase.table("workflows").delete().eq(
            "id", workflow_id
        ).eq("user_id", user_id).execute()

        return True

    except Exception as e:
        raise Exception(f"Error deleting workflow: {str(e)}")


def archive_workflow(workflow_id: str, user_id: str) -> Dict[str, Any]:
    """Archive a workflow (soft delete)."""
    return update_workflow(workflow_id, user_id, {"status": "archived"})


def get_workflow_count(user_id: str, status: Optional[str] = None) -> int:
    """Get count of workflows for a user."""
    try:
        query = supabase.table("workflows").select("id", count="exact").eq("user_id", user_id)

        if status:
            query = query.eq("status", status)

        response = query.execute()

        return response.count if hasattr(response, 'count') else 0

    except Exception as e:
        raise Exception(f"Error counting workflows: {str(e)}")
