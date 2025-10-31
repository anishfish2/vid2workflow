"""Chat-based workflow completion endpoint."""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import json
from openai import OpenAI
import os
from dotenv import load_dotenv
from supabase import create_client, Client
from middleware.auth import require_auth

load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL") or "http://localhost:54321"
SUPABASE_SERVICE_KEY = os.getenv("SUPABASE_SERVICE_KEY") or "your-service-key"

# Supabase client
supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SERVICE_KEY
)

# Import services for function calling
from services.google_api_service import read_sheet_range
from pydantic import BaseModel as PydanticBaseModel


class ChatMessage(BaseModel):
    role: str
    content: str


class WorkflowChatRequest(BaseModel):
    workflow_draft_id: str
    message: str
    conversation_history: List[ChatMessage] = []


# Define available functions for LLM to call
AVAILABLE_FUNCTIONS = {
    # Google Sheets
    "inspect_google_sheet": {
        "description": "Inspect a Google Sheet to get headers, column names, and sample data",
        "parameters": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string", "description": "The Google Sheets ID"},
                "sample_rows": {"type": "integer", "description": "Number of sample rows to return", "default": 5}
            },
            "required": ["spreadsheet_id"]
        }
    },
    "read_google_sheet": {
        "description": "Read data from a Google Sheets range",
        "parameters": {
            "type": "object",
            "properties": {
                "spreadsheet_id": {"type": "string"},
                "range": {"type": "string", "description": "Range in A1 notation (e.g., 'Sheet1!A1:B10')"}
            },
            "required": ["spreadsheet_id", "range"]
        }
    },
    "save_workflow_parameter": {
        "description": "Save a workflow parameter that the user provided. Call this whenever the user gives you information needed for the workflow.",
        "parameters": {
            "type": "object",
            "properties": {
                "step_index": {"type": "integer", "description": "Which step this parameter is for (0-indexed)"},
                "parameter_name": {"type": "string", "description": "Name of the parameter (e.g., 'spreadsheet_id', 'column', 'range', 'email_column')"},
                "parameter_value": {"type": "string", "description": "The value the user provided"}
            },
            "required": ["step_index", "parameter_name", "parameter_value"]
        }
    },
    "mark_workflow_complete": {
        "description": "IMPORTANT: Call this function when you have collected ALL required information and are ready to create the workflow. This signals that the workflow is complete and ready to be published.",
        "parameters": {
            "type": "object",
            "properties": {
                "summary": {"type": "string", "description": "A brief summary of what the workflow will do"}
            },
            "required": ["summary"]
        }
    }
}


def get_function_definitions() -> List[Dict[str, Any]]:
    """Convert AVAILABLE_FUNCTIONS to OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": func["description"],
                "parameters": func["parameters"]
            }
        }
        for name, func in AVAILABLE_FUNCTIONS.items()
    ]


async def call_function(function_name: str, arguments: Dict[str, Any], user_id: str) -> Dict[str, Any]:
    """Execute a function call from the LLM."""
    if function_name not in AVAILABLE_FUNCTIONS:
        return {"error": f"Function {function_name} not found"}

    try:
        if function_name == "inspect_google_sheet":
            spreadsheet_id = arguments.get("spreadsheet_id")
            sample_rows = arguments.get("sample_rows", 5)

            headers_data = read_sheet_range(user_id, spreadsheet_id, "1:1")
            if not headers_data or "values" not in headers_data or not headers_data["values"]:
                return {"success": False, "error": "Could not read sheet headers"}

            headers = headers_data["values"][0] if headers_data["values"] else []

            # Create column mapping
            column_map = {}
            for idx, header in enumerate(headers):
                col_letter = chr(65 + idx)
                column_map[col_letter] = header if header else f"Column {col_letter}"

            # Read sample data
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

            return {
                "success": True,
                "data": {
                    "spreadsheet_id": spreadsheet_id,
                    "headers": column_map,
                    "sample_data": sample_data,
                    "total_columns": len(headers),
                    "sample_row_count": len(sample_data)
                }
            }

        elif function_name == "read_google_sheet":
            spreadsheet_id = arguments.get("spreadsheet_id")
            range_str = arguments.get("range")

            result = read_sheet_range(user_id, spreadsheet_id, range_str)
            return {"success": True, "data": result}

        elif function_name == "save_workflow_parameter":
            # This is handled in the main workflow_chat function
            # Just return success - the parameter will be saved to collected_params
            return {
                "success": True,
                "message": "Parameter saved",
                "step_index": arguments.get("step_index"),
                "parameter_name": arguments.get("parameter_name"),
                "parameter_value": arguments.get("parameter_value")
            }

        elif function_name == "mark_workflow_complete":
            # Workflow is complete! This is a signal to finish
            return {
                "success": True,
                "workflow_complete": True,
                "summary": arguments.get("summary")
            }

        else:
            return {"error": f"Function {function_name} not implemented"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/workflow-chat")
async def workflow_chat(
    request: WorkflowChatRequest,
    current_user: dict = Depends(require_auth)
):
    """
    Chat-based workflow completion.

    The LLM asks questions one by one and can call backend routes
    to get information (like inspecting sheets for column headers).
    """
    try:
        user_id = current_user["user_id"]

        # Get workflow draft
        result = supabase.table("workflows").select("*").eq("id", request.workflow_draft_id).execute()
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Workflow draft not found")

        workflow_draft = result.data[0]

        # Parse steps - might be dict with raw_text or list
        steps_raw = workflow_draft.get("steps", [])
        print(f"Steps raw type: {type(steps_raw)}")

        try:
            if isinstance(steps_raw, dict) and "raw_text" in steps_raw:
                # Steps stored as {"raw_text": "[...]"}
                print(f"Parsing from raw_text, length: {len(steps_raw['raw_text'])}")
                workflow_steps = json.loads(steps_raw["raw_text"])
            elif isinstance(steps_raw, str):
                # Steps stored as JSON string
                print(f"Parsing from string, length: {len(steps_raw)}")
                workflow_steps = json.loads(steps_raw)
            elif isinstance(steps_raw, list):
                # Steps already a list
                print(f"Already a list with {len(steps_raw)} items")
                workflow_steps = steps_raw
            else:
                print(f"Unknown format: {type(steps_raw)}")
                workflow_steps = []
        except json.JSONDecodeError as e:
            print(f"JSON decode error: {e}")
            print(f"Attempting to use steps_raw directly if it's a list...")
            # Fallback: if it's actually a list inside the dict, use it
            if isinstance(steps_raw, dict):
                workflow_steps = steps_raw if isinstance(steps_raw, list) else []
            else:
                workflow_steps = []

        missing_info = workflow_draft.get("missing_info", [])
        collected_params = workflow_draft.get("collected_params", {})

        # Build conversation context
        system_prompt = f"""You are a helpful workflow automation assistant. Your job is to gather the necessary information from the user to complete their workflow.

WORKFLOW STEPS:
{json.dumps(workflow_steps, indent=2)}

MISSING INFORMATION NEEDED:
{json.dumps(missing_info, indent=2)}

INFORMATION ALREADY COLLECTED:
{json.dumps(collected_params, indent=2)}

YOUR TASK:
1. Ask the user questions ONE AT A TIME to gather the missing information
2. Be conversational and friendly
3. Use the available functions to inspect resources (like sheets) to help the user
4. When you need to know what columns are in a sheet, call inspect_google_sheet
5. **CRITICAL**: Whenever the user provides a parameter value, immediately call save_workflow_parameter to store it
6. Keep track of what information you've collected
7. When ALL required information is collected, call mark_workflow_complete with a summary, then tell the user

CRITICAL RULES:
- **NEVER make assumptions or use example values**
- **NEVER use placeholder values like "abc123" or "example_id"**
- **ONLY use values that the user EXPLICITLY provides in their messages**
- If you don't have a value, ASK the user for it - do NOT make one up
- Only ask for information that's actually MISSING
- If the user provides an ID (like spreadsheet_id), IMMEDIATELY call save_workflow_parameter to save it, THEN call inspect_google_sheet
- Be specific about what you're asking for (e.g., "Which column contains the email addresses?" not just "What column?")
- Don't ask for the same information twice
- **ALWAYS call save_workflow_parameter when the user gives you a value** - this is how parameters get saved!
- **CRITICAL**: When you have ALL information, you MUST call mark_workflow_complete() - this is what triggers workflow creation!

GOOGLE SHEETS RANGE FORMAT:
- Valid: "C2:C6", "A1:B10", "B2:B1000"
- INVALID: "Sheet1!C2:C", "C2:C" (open-ended), "Team Contacts 2024-2025!C2:C6"
- Remove sheet name prefix - ALWAYS use just column and row format
- If user says "column C rows 2-6" → use "C2:C6"
- If user says "column C from row 2" → use "C2:C1000"

CRITICAL - SAVING VALUES:
- ALWAYS save the EXACT value the user provides
- For spreadsheet_id: save the FULL ID string (like "1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
- DO NOT use placeholders like "detected_id" or "user_provided_id"
- DO NOT abstract or summarize values - use EXACT strings

EXAMPLE FLOW:
User: "My spreadsheet ID is 1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms"
You: Call save_workflow_parameter(step_index=0, parameter_name="spreadsheet_id", parameter_value="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
You: Call inspect_google_sheet(spreadsheet_id="1BxiMVs0XRA5nFMdKvBdBZjgmUUqptlbs74OgvE2upms")
You: "Great! I can see your sheet has columns A (Name), B (Email), C (Phone). Which column contains the data?"
User: "Column C, rows 2 to 6"
You: Call save_workflow_parameter(step_index=0, parameter_name="range", parameter_value="C2:C6")
You: Call mark_workflow_complete(summary="Read data from C2:C6")
You: "Perfect! I have everything I need. Creating your workflow now..."
"""

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})

        # Add user's new message
        messages.append({"role": "user", "content": request.message})

        # Call LLM with function calling
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            tools=get_function_definitions(),
            tool_choice="auto",
            temperature=0.7
        )

        assistant_message = response.choices[0].message

        # Handle function calls
        if assistant_message.tool_calls:
            # Execute function calls
            function_responses = []
            is_complete = False  # Track if LLM marked workflow complete

            for tool_call in assistant_message.tool_calls:
                function_name = tool_call.function.name
                arguments = json.loads(tool_call.function.arguments)

                print(f"LLM calling function: {function_name} with args: {arguments}")

                # Execute the function
                result = await call_function(function_name, arguments, user_id)

                function_responses.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": function_name,
                    "content": json.dumps(result)
                })

                # Update collected params if this was a save_workflow_parameter call
                if function_name == "save_workflow_parameter":
                    step_idx = arguments.get("step_index")
                    param_name = arguments.get("parameter_name")
                    param_value = arguments.get("parameter_value")

                    # Store in step-indexed format
                    if step_idx not in collected_params:
                        collected_params[step_idx] = {}
                    collected_params[step_idx][param_name] = param_value

                    print(f"Saved parameter: step_{step_idx}.{param_name} = {param_value}")

                # Check if workflow was marked complete
                if function_name == "mark_workflow_complete":
                    is_complete = True
                    print(f"✅ Workflow marked as complete by LLM!")

            # Add function results to conversation and get final response
            messages.append(assistant_message)
            messages.extend(function_responses)

            # Get LLM's response after function calls
            second_response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                temperature=0.7
            )

            final_message = second_response.choices[0].message.content

            # Check if workflow is complete (check message text OR if mark_workflow_complete was called)
            if not is_complete:  # Only check message if not already marked complete
                is_complete = "creating your workflow now" in final_message.lower() or "all the information" in final_message.lower()

            # Update collected params in database
            supabase.table("workflows").update({
                "collected_params": collected_params
            }).eq("id", request.workflow_draft_id).execute()

            return {
                "message": final_message,
                "function_calls": [
                    {
                        "name": tc.function.name,
                        "arguments": json.loads(tc.function.arguments)
                    }
                    for tc in assistant_message.tool_calls
                ],
                "complete": is_complete  # ← Now properly detects completion!
            }
        else:
            # No function calls, just return the message
            response_text = assistant_message.content

            # Check if workflow is complete
            is_complete = "creating your workflow now" in response_text.lower() or "all the information" in response_text.lower()

            # Extract collected parameters from user's message
            # (Simple extraction - in production, use LLM to parse)
            # For now, we'll rely on the LLM to call functions which updates collected_params

            return {
                "message": response_text,
                "function_calls": [],
                "complete": is_complete
            }

    except Exception as e:
        print(f"Error in workflow chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class WorkflowCompleteRequest(BaseModel):
    workflow_draft_id: str


@router.post("/workflow-chat/complete")
async def complete_workflow_from_chat(
    request: WorkflowCompleteRequest,
    current_user: dict = Depends(require_auth)
):
    """
    Called when the chat is complete to finalize the workflow.
    """
    try:
        workflow_draft_id = request.workflow_draft_id

        result = supabase.table("workflows").select("*").eq("id", workflow_draft_id).execute()
        if not result.data:
            raise HTTPException(status_code=404, detail="Workflow draft not found")

        workflow_draft = result.data[0]

        print("in workflow-creation\n", json.dumps(workflow_draft, indent=2, ensure_ascii=False))

        # Parse steps - might be dict with raw_text or list
        steps_raw = workflow_draft.get("steps", [])
        if isinstance(steps_raw, dict) and "raw_text" in steps_raw:
            # Steps stored as {"raw_text": "[...]"}
            workflow_steps = json.loads(steps_raw["raw_text"])
        elif isinstance(steps_raw, str):
            # Steps stored as JSON string
            workflow_steps = json.loads(steps_raw)
        elif isinstance(steps_raw, list):
            # Steps already a list
            workflow_steps = steps_raw
        else:
            workflow_steps = []

        collected_params_raw = workflow_draft.get("collected_params", {})

        if isinstance(collected_params_raw, str):
            collected_params_raw = json.loads(collected_params_raw)

        collected_params = {}
        for key, value in collected_params_raw.items():
            try:
                collected_params[int(key)] = value
            except (ValueError, TypeError):
                collected_params[key] = value

        from lib.workflow_planner import enrich_steps_with_data, generate_n8n_workflow_with_complete_info

        print(f"Collected params (parsed): {collected_params}")
        print(f"Workflow steps type: {type(workflow_steps)}, content: {workflow_steps}")

        enriched_steps = enrich_steps_with_data(workflow_steps, collected_params)
        print(f"Enriched steps: {enriched_steps}")

        final_workflow = generate_n8n_workflow_with_complete_info(
            steps=enriched_steps,
            workflow_name=workflow_draft.get("name", "Generated Workflow").replace(" (Pending)", ""),
            user_id=current_user["user_id"]
        )

        print(f"Generated n8n workflow: {json.dumps(final_workflow, indent=2)}")

        # Create workflow in n8n
        import requests
        N8N_API_KEY = os.getenv("N8N_API_KEY", "your-api-key")
        N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")

        headers = {
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json",
        }

        url = N8N_BASE_URL.rstrip("/") + "/workflows"
        print(f"Publishing workflow to n8n at: {url}")

        n8n_workflow_id = None
        n8n_workflow_url = None
        n8n_error = None

        try:
            response = requests.post(url, headers=headers, json=final_workflow, timeout=10)
            print(f"n8n response status: {response.status_code}")
            print(f"n8n response body: {response.text}")

            if response.status_code == 200:
                n8n_response = response.json()
                n8n_workflow_id = n8n_response.get("id")
                n8n_workflow_url = f"{N8N_BASE_URL.replace('/api/v1', '')}/workflow/{n8n_workflow_id}"
                print(f"✅ Workflow created in n8n: {n8n_workflow_url}")
            else:
                n8n_error = f"n8n API returned {response.status_code}: {response.text}"
                print(f"⚠️ Failed to create workflow in n8n: {n8n_error}")

        except Exception as e:
            n8n_error = str(e)
            print(f"⚠️ Error calling n8n API: {n8n_error}")

        # Update the workflow in database
        supabase.table("workflows").update({
            "steps": enriched_steps,
            "n8n_workflow_data": final_workflow,
            "n8n_workflow_id": n8n_workflow_id,
            "status": "active",
            "name": workflow_draft.get("name", "").replace(" (Pending)", "")
        }).eq("id", workflow_draft_id).execute()

        return {
            "success": True,
            "workflow_id": workflow_draft_id,
            "workflow_json": final_workflow,
            "n8n_workflow_id": n8n_workflow_id,
            "n8n_workflow_url": n8n_workflow_url,
            "n8n_error": n8n_error
        }

    except Exception as e:
        print(f"Error completing workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
