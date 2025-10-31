from fastapi import APIRouter
from models.tools import ToolRequest, ToolResponse
from services.google_api_service import (
    read_sheet_range,
    write_sheet_range,
    append_sheet_data,
    create_spreadsheet,
    clear_sheet_range
)
from typing import Dict, List
from pydantic import BaseModel

router = APIRouter()

# Google Sheets Operations

class SheetInspectRequest(BaseModel):
    user_id: str
    spreadsheet_id: str
    sample_rows: int = 5  # How many sample rows to return

@router.post("/inspect")
async def inspect_sheet_api(request: SheetInspectRequest):
    """Inspect a Google Sheet to get headers, columns, and sample data"""
    try:
        user_id = request.user_id
        spreadsheet_id = request.spreadsheet_id
        sample_rows = request.sample_rows

        print(f"Inspecting sheet {spreadsheet_id} for user {user_id}")

        headers_data = read_sheet_range(user_id, spreadsheet_id, "1:1")

        print(headers_data)

        if not headers_data or "values" not in headers_data or not headers_data["values"]:
            print("Could not read sheet headers. The sheet might be empty.")
            return ToolResponse(
                success=False,
                error="Could not read sheet headers. The sheet might be empty.",
                retryable=True
            )

        headers = headers_data["values"][0] if headers_data["values"] else []

        # Create column mapping (A, B, C, etc. -> header names)
        column_map = {}
        for idx, header in enumerate(headers):
            col_letter = chr(65 + idx)  # A=65 in ASCII
            column_map[col_letter] = header if header else f"Column {col_letter}"

        # Read sample data (next N rows after header)
        sample_range = f"2:{sample_rows + 1}"
        sample_data_result = read_sheet_range(user_id, spreadsheet_id, sample_range)

        sample_data = []
        if sample_data_result and "values" in sample_data_result:
            for row in sample_data_result["values"]:
                row_data = {}
                for idx, value in enumerate(row):
                    col_letter = chr(65 + idx)
                    row_data[col_letter] = value
                sample_data.append(row_data)

        return ToolResponse(
            success=True,
            data={
                "spreadsheet_id": spreadsheet_id,
                "headers": column_map,
                "sample_data": sample_data,
                "total_columns": len(headers),
                "sample_row_count": len(sample_data)
            }
        )

    except Exception as e:
        print(f"Error inspecting sheet: {str(e)}")
        return ToolResponse(
            success=False,
            error=f"Failed to inspect sheet: {str(e)}",
            retryable=True
        )

class SmartSearchRequest(BaseModel):
    user_id: str
    spreadsheet_id: str
    data_type: str  # "email", "phone", "name", "number", "url", etc.
    start_row: int = 2
    end_row: int = None

@router.post("/smart-search")
async def smart_search_sheet_api(request: SmartSearchRequest):
    """Search entire sheet for specific data type (emails, phones, etc.) across all columns"""
    try:
        user_id = request.user_id
        spreadsheet_id = request.spreadsheet_id
        data_type = request.data_type.lower()
        start_row = request.start_row
        end_row = request.end_row

        print(f"Smart searching sheet {spreadsheet_id} for {data_type}")

        # Read all data from the sheet
        range_str = f"{start_row}:{end_row}" if end_row else f"{start_row}:1000"
        data = read_sheet_range(user_id, spreadsheet_id, range_str)

        if not data or "values" not in data:
            return ToolResponse(
                success=False,
                error="Could not read sheet data",
                retryable=True
            )

        # Define patterns for different data types
        import re
        patterns = {
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b(?:\+?1[-.]?)?\(?\d{3}\)?[-.]?\d{3}[-.]?\d{4}\b',
            "url": r'https?://[^\s]+',
            "number": r'\b\d+\.?\d*\b',
        }

        pattern = patterns.get(data_type)
        if not pattern:
            return ToolResponse(
                success=False,
                error=f"Unsupported data type: {data_type}. Supported: {', '.join(patterns.keys())}",
                retryable=False
            )

        # Search all cells for matching data
        found_items = []
        found_columns = set()

        for row_idx, row in enumerate(data["values"]):
            for col_idx, cell in enumerate(row):
                if cell and re.search(pattern, str(cell)):
                    col_letter = chr(65 + col_idx)
                    found_items.append({
                        "value": cell,
                        "row": start_row + row_idx,
                        "column": col_letter
                    })
                    found_columns.add(col_letter)

        # Deduplicate values
        unique_values = list(set([item["value"] for item in found_items]))

        return ToolResponse(
            success=True,
            data={
                "data_type": data_type,
                "found_items": found_items[:100],  # Limit to first 100
                "unique_values": unique_values[:100],
                "total_found": len(found_items),
                "columns_with_data": sorted(list(found_columns)),
                "recommended_columns": sorted(list(found_columns))[:3]  # Top 3 columns
            }
        )

    except Exception as e:
        print(f"Error in smart search: {str(e)}")
        return ToolResponse(
            success=False,
            error=f"Failed to search sheet: {str(e)}",
            retryable=True
        )

@router.post("/read")
async def read_sheet_api(request: ToolRequest):
    """Read data from a Google Sheets range"""

    print("GOT HERE")
    try:
        user_id = request.user_id
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

@router.post("/write")
async def write_sheet_api(request: ToolRequest):
    """Write data to a Google Sheets range"""
    try:
        user_id = request.user_id
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

@router.post("/append")
async def append_sheet_api(request: ToolRequest):
    """Append data to a Google Sheet"""
    try:
        user_id = request.user_id
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

@router.post("/create")
async def create_spreadsheet_api(request: ToolRequest):
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

@router.post("/clear")
async def clear_sheet_api(request: ToolRequest):
    """Clear a range in Google Sheets"""
    try:
        user_id = request.user_id
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

@router.post("/copy")
async def copy_sheet_api(request: ToolRequest):
    """Copy data from one range (read operation)"""
    try:
        user_id = request.user_id
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
