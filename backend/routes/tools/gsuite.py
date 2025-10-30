from fastapi import APIRouter, Depends
from models.tools import ToolRequest, ToolResponse
from middleware.auth import require_auth
from services.google_api_service import (
    read_sheet_range,
    write_sheet_range,
    append_sheet_data,
    create_spreadsheet,
    clear_sheet_range
)
from typing import Dict

router = APIRouter()

# Google Sheets Operations

@router.post("/sheets/read")
async def read_sheet_api(request: ToolRequest, user: Dict = Depends(require_auth)):
    """Read data from a Google Sheets range"""
    try:
        user_id = user["user_id"]
        spreadsheet_id = request.params.get("spreadsheet_id")
        range_notation = request.params.get("range", "A1:Z100")

        if not spreadsheet_id:
            return ToolResponse(success=False, error="spreadsheet_id is required", retryable=False)

        print(f"Reading sheet {spreadsheet_id} range {range_notation} for user {user_id}")

        # Call real Google Sheets API
        data = read_sheet_range(user_id, spreadsheet_id, range_notation)

        return ToolResponse(
            success=True,
            data=data
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )

@router.post("/sheets/write")
async def write_sheet_api(request: ToolRequest, user: Dict = Depends(require_auth)):
    """Write data to a Google Sheets range"""
    try:
        user_id = user["user_id"]
        spreadsheet_id = request.params.get("spreadsheet_id")
        range_notation = request.params.get("range", "A1")
        values = request.params.get("values", [])

        if not spreadsheet_id:
            return ToolResponse(success=False, error="spreadsheet_id is required", retryable=False)

        print(f"Writing to sheet {spreadsheet_id} range {range_notation} for user {user_id}")

        data = write_sheet_range(user_id, spreadsheet_id, range_notation, values)

        return ToolResponse(
            success=True,
            data=data
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )

@router.post("/sheets/append")
async def append_sheet_api(request: ToolRequest, user: Dict = Depends(require_auth)):
    """Append data to a Google Sheet"""
    try:
        user_id = user["user_id"]
        spreadsheet_id = request.params.get("spreadsheet_id")
        range_notation = request.params.get("range", "A1")
        values = request.params.get("values", [])

        if not spreadsheet_id:
            return ToolResponse(success=False, error="spreadsheet_id is required", retryable=False)

        print(f"Appending to sheet {spreadsheet_id} for user {user_id}")

        data = append_sheet_data(user_id, spreadsheet_id, range_notation, values)

        return ToolResponse(
            success=True,
            data=data
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )

@router.post("/sheets/create")
async def create_spreadsheet_api(request: ToolRequest, user: Dict = Depends(require_auth)):
    """Create a new Google Spreadsheet"""
    try:
        user_id = user["user_id"]
        title = request.params.get("title", "New Spreadsheet")
        sheet_titles = request.params.get("sheet_titles", None)

        print(f"Creating spreadsheet '{title}' for user {user_id}")

        data = create_spreadsheet(user_id, title, sheet_titles)

        return ToolResponse(
            success=True,
            data=data
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=False
        )

@router.post("/sheets/clear")
async def clear_sheet_api(request: ToolRequest, user: Dict = Depends(require_auth)):
    """Clear a range in Google Sheets"""
    try:
        user_id = user["user_id"]
        spreadsheet_id = request.params.get("spreadsheet_id")
        range_notation = request.params.get("range", "A1:Z100")

        if not spreadsheet_id:
            return ToolResponse(success=False, error="spreadsheet_id is required", retryable=False)

        print(f"Clearing sheet {spreadsheet_id} range {range_notation} for user {user_id}")

        data = clear_sheet_range(user_id, spreadsheet_id, range_notation)

        return ToolResponse(
            success=True,
            data=data
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )

@router.post("/sheets/copy")
async def copy_sheet_api(request: ToolRequest, user: Dict = Depends(require_auth)):
    """Copy data from one range (read operation)"""
    try:
        user_id = user["user_id"]
        spreadsheet_id = request.params.get("spreadsheet_id")
        source_range = request.params.get("source_range")

        if not spreadsheet_id or not source_range:
            return ToolResponse(success=False, error="spreadsheet_id and source_range are required", retryable=False)

        print(f"Copying from {source_range} in sheet {spreadsheet_id} for user {user_id}")

        # Read the data from source range
        data = read_sheet_range(user_id, spreadsheet_id, source_range)

        return ToolResponse(
            success=True,
            data={
                "copied_values": data.get("values", []),
                "source_range": source_range
            }
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )