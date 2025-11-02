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
    },
    "modify_workflow_steps": {
        "description": "Modify the workflow by adding, removing, or editing steps. Use this when the user requests changes to the workflow logic (e.g., 'add a step to summarize the data', 'remove the duplicate filter', 'change the email body to include X'). You have FULL CONTROL to restructure the workflow as needed.",
        "parameters": {
            "type": "object",
            "properties": {
                "modified_steps": {
                    "type": "array",
                    "description": "The complete updated list of workflow steps. Each step should have: action, service, operation, and parameters fields.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "action": {"type": "string", "description": "Human-readable description of what this step does"},
                            "service": {"type": "string", "description": "Service name (e.g., 'googleSheets', 'gmail', 'function', 'code')"},
                            "operation": {"type": "string", "description": "Operation to perform"},
                            "parameters": {"type": "object", "description": "Parameters for this operation"}
                        },
                        "required": ["action", "service", "operation", "parameters"]
                    }
                },
                "change_summary": {
                    "type": "string",
                    "description": "Brief description of what was changed (e.g., 'Added a summarization step before sending email')"
                }
            },
            "required": ["modified_steps", "change_summary"]
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

        elif function_name == "modify_workflow_steps":
            # Update the workflow steps in the database
            modified_steps = arguments.get("modified_steps")
            change_summary = arguments.get("change_summary")

            # Note: The workflow_draft_id needs to be passed from the context
            # For now, we'll return the modified steps and handle the update in the main function
            return {
                "success": True,
                "modified_steps": modified_steps,
                "change_summary": change_summary,
                "message": f"Workflow modified: {change_summary}"
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

        try:
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
        except json.JSONDecodeError as e:
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
7. **IMPORTANT**: If the user requests changes to the workflow logic (e.g., "make the email body a summary of the sheet", "add a filter step", "remove this step"), use modify_workflow_steps to restructure the workflow
8. When ALL required information is collected, call mark_workflow_complete with a summary, then tell the user

WORKFLOW MODIFICATION CAPABILITIES:
- You have FULL CONTROL to modify the workflow structure
- Use modify_workflow_steps when the user asks to:
  - Add new steps (e.g., "add a summarization step", "include data processing")
  - Remove steps (e.g., "skip the duplicate check")
  - Change step logic (e.g., "make the email body include sheet data", "filter by a different criteria")
  - Reorder steps
- When modifying, provide the COMPLETE updated list of steps with all changes applied
- Available services: googleSheets, gmail, function, code, http, itemLists, llm
- **IMPORTANT - LLM Service**: For AI tasks (summarization, classification, text generation, etc.), use the "llm" service:
  - service: "llm"
  - operation: "process"
  - parameters: {{
      "prompt": "Clear instruction for the LLM (e.g., 'Summarize this data', 'Extract email addresses', 'Classify sentiment')",
      "model": "gpt-4o-mini" (or "gpt-4o" for more complex tasks),
      "temperature": 0.7,
      "max_tokens": 2000
    }}
  - The LLM node will receive data from previous steps and process it according to the prompt
  - Example: {{"action": "Summarize sheet data", "service": "llm", "operation": "process", "parameters": {{"prompt": "Create a brief summary of the following data", "model": "gpt-4o-mini"}}}}
- For complex data transformations or AI tasks, PREFER using service="llm" over service="code"

CRITICAL RULES:
- **NEVER make assumptions or use example values**
- **NEVER use placeholder values like "abc123" or "example_id"**
- **ONLY use values that the user EXPLICITLY provides in their messages**
- If you don't have a value, ASK the user for it - do NOT make one up
- Only ask for information that's actually MISSING
- If the user provides an ID (like spreadsheet_id), IMMEDIATELY call save_workflow_parameter to save it, THEN call inspect_google_sheet
- Be specific about what you're asking for (e.g., "Which column contains the email addresses?" not just "What column?")
- When user requests workflow changes, first acknowledge the request, then call modify_workflow_steps with the updated workflow
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

                # Check if workflow was marked complete
                if function_name == "mark_workflow_complete":
                    is_complete = True

                # Handle workflow modification
                if function_name == "modify_workflow_steps":
                    modified_steps = result.get("modified_steps")
                    change_summary = result.get("change_summary")

                    if modified_steps:
                        # Update workflow steps in database
                        workflow_steps = modified_steps  # Update local copy
                        supabase.table("workflows").update({
                            "steps": modified_steps
                        }).eq("id", request.workflow_draft_id).execute()

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


class WorkflowEditChatRequest(BaseModel):
    workflow_id: str
    message: str
    conversation_history: List[ChatMessage] = []


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

        enriched_steps = enrich_steps_with_data(workflow_steps, collected_params)

        final_workflow = generate_n8n_workflow_with_complete_info(
            steps=enriched_steps,
            workflow_name=workflow_draft.get("name", "Generated Workflow").replace(" (Pending)", ""),
            user_id=current_user["user_id"]
        )

        # Create workflow in n8n
        import requests
        N8N_API_KEY = os.getenv("N8N_API_KEY", "your-api-key")
        N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")

        headers = {
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json",
        }

        url = N8N_BASE_URL.rstrip("/") + "/workflows"

        n8n_workflow_id = None
        n8n_workflow_url = None
        n8n_error = None

        try:
            response = requests.post(url, headers=headers, json=final_workflow, timeout=10)

            if response.status_code == 200:
                n8n_response = response.json()
                n8n_workflow_id = n8n_response.get("id")
                n8n_workflow_url = f"{N8N_BASE_URL.replace('/api/v1', '')}/workflow/{n8n_workflow_id}"
            else:
                n8n_error = f"n8n API returned {response.status_code}: {response.text}"

        except Exception as e:
            n8n_error = str(e)

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


# Workflow editing functions
WORKFLOW_EDIT_FUNCTIONS = {
    "get_workflow_structure": {
        "description": "Get the current structure of the workflow including all nodes and their configuration",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "add_node": {
        "description": "Add a new node to the workflow. Use this when the user wants to add a step (e.g., 'add a node that reads the google sheet')",
        "parameters": {
            "type": "object",
            "properties": {
                "node_type": {
                    "type": "string",
                    "description": "Type of node (e.g., 'httpRequest', 'code', 'set', 'if', 'merge')",
                    "enum": ["httpRequest", "code", "set", "if", "merge", "splitInBatches"]
                },
                "name": {
                    "type": "string",
                    "description": "Human-readable name for the node"
                },
                "parameters": {
                    "type": "object",
                    "description": "Node-specific parameters"
                },
                "position_after": {
                    "type": "string",
                    "description": "Name or ID of the node to insert this after (leave empty to add at the end)"
                }
            },
            "required": ["node_type", "name", "parameters"]
        }
    },
    "modify_node": {
        "description": "Modify an existing node's parameters or configuration. Can update both node properties (like name) and node parameters (like jsCode, url, etc.)",
        "parameters": {
            "type": "object",
            "properties": {
                "node_identifier": {
                    "type": "string",
                    "description": "Name or ID of the node to modify"
                },
                "updates": {
                    "type": "object",
                    "description": "Parameters to update (e.g., jsCode, url, method, jsonBody)"
                },
                "new_name": {
                    "type": "string",
                    "description": "Optional: New name for the node (e.g., 'Process All Sheet Data')"
                }
            },
            "required": ["node_identifier", "updates"]
        }
    },
    "delete_node": {
        "description": "Delete a node from the workflow",
        "parameters": {
            "type": "object",
            "properties": {
                "node_identifier": {
                    "type": "string",
                    "description": "Name or ID of the node to delete"
                }
            },
            "required": ["node_identifier"]
        }
    },
    "get_workflow_connections": {
        "description": "Get detailed information about how nodes are connected in the workflow. Shows which nodes connect to which, and identifies any disconnected nodes.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    "connect_nodes": {
        "description": "Connect two nodes together. Creates a connection from the source node's output to the target node's input.",
        "parameters": {
            "type": "object",
            "properties": {
                "source_node": {
                    "type": "string",
                    "description": "Name or ID of the source node (the node that outputs data)"
                },
                "target_node": {
                    "type": "string",
                    "description": "Name or ID of the target node (the node that receives data)"
                },
                "source_output": {
                    "type": "string",
                    "description": "Output type (default: 'main')",
                    "default": "main"
                },
                "target_input_index": {
                    "type": "integer",
                    "description": "Target input index (default: 0)",
                    "default": 0
                }
            },
            "required": ["source_node", "target_node"]
        }
    },
    "rebuild_workflow_connections": {
        "description": "Clear all connections and rebuild them by connecting nodes in sequential order. Use this when connections exist in database but not in n8n, or when you need to force a refresh.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
}


def get_workflow_edit_function_definitions() -> List[Dict[str, Any]]:
    """Convert WORKFLOW_EDIT_FUNCTIONS to OpenAI function calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": func["description"],
                "parameters": func["parameters"]
            }
        }
        for name, func in WORKFLOW_EDIT_FUNCTIONS.items()
    ]


def validate_and_fix_connections(workflow_data: Dict[str, Any]) -> None:
    """Validate and fix workflow connections to ensure they reference valid nodes."""
    n8n_workflow = workflow_data.get("n8n_workflow_data", {})
    if not n8n_workflow or "nodes" not in n8n_workflow:
        return

    nodes = n8n_workflow["nodes"]
    connections = n8n_workflow.get("connections", {})

    valid_node_ids = {node["id"] for node in nodes}
    valid_node_names = {node["name"] for node in nodes}

    cleaned_connections = {}
    for source_key, connection_data in connections.items():
        source_exists = source_key in valid_node_ids or source_key in valid_node_names

        if not source_exists:
            continue

        cleaned_connection_data = {}
        for connection_type, connection_list in connection_data.items():
            cleaned_list = []
            for connection_group in connection_list:
                cleaned_group = []
                for conn in connection_group:
                    target_key = conn.get("node")
                    target_exists = target_key in valid_node_ids or target_key in valid_node_names

                    if target_exists:
                        cleaned_group.append(conn)
                if cleaned_group:
                    cleaned_list.append(cleaned_group)
            if cleaned_list:
                cleaned_connection_data[connection_type] = cleaned_list

        if cleaned_connection_data:
            cleaned_connections[source_key] = cleaned_connection_data

    print(f"Cleaned connections: {cleaned_connections}")
    n8n_workflow["connections"] = cleaned_connections


async def call_workflow_edit_function(
    function_name: str,
    arguments: Dict[str, Any],
    user_id: str,
    workflow_data: Dict[str, Any]
) -> Dict[str, Any]:
    """Execute a workflow editing function."""
    if function_name not in WORKFLOW_EDIT_FUNCTIONS:
        return {"error": f"Function {function_name} not found"}

    try:
        if function_name == "get_workflow_structure":
            # Return the current workflow structure
            n8n_workflow = workflow_data.get("n8n_workflow_data", {})
            nodes = n8n_workflow.get("nodes", [])

            # Simplify node info for the LLM
            simplified_nodes = []
            for node in nodes:
                node_info = {
                    "name": node.get("name"),  # This is what you use for node_identifier!
                    "type": node.get("type"),
                    "parameters": node.get("parameters", {})
                }
                simplified_nodes.append(node_info)

            return {
                "success": True,
                "nodes": simplified_nodes,
                "total_nodes": len(nodes),
                "instruction": "To modify a node, use its 'name' field as the node_identifier in modify_node()"
            }

        elif function_name == "add_node":
            # Add a new node to the workflow
            n8n_workflow = workflow_data.get("n8n_workflow_data", {})
            if not n8n_workflow or "nodes" not in n8n_workflow:
                return {"error": "No valid workflow data found"}

            nodes = n8n_workflow["nodes"]
            connections = n8n_workflow.get("connections", {})

            # Generate unique ID for new node
            import uuid
            new_node_id = str(uuid.uuid4())[:8]

            # Determine position
            if nodes:
                last_node = nodes[-1]
                position = [last_node["position"][0] + 300, last_node["position"][1]]
            else:
                position = [250, 300]

            # Create node based on type
            node_type = arguments.get("node_type")
            node_name = arguments.get("name")
            node_params = arguments.get("parameters", {})

            new_node = {
                "id": new_node_id,
                "name": node_name,
                "type": f"n8n-nodes-base.{node_type}",
                "typeVersion": 4.2 if node_type == "httpRequest" else 2,
                "position": position,
                "parameters": node_params
            }

            # Add node
            nodes.append(new_node)

            # Connect to previous node if position_after is specified or add at end
            position_after = arguments.get("position_after")
            if position_after:
                # Find the node to connect after
                prev_node = next((n for n in nodes if n["name"] == position_after or n["id"] == position_after), None)
                if prev_node:
                    prev_node_id = prev_node["id"]
                    # Create connection
                    if prev_node_id not in connections:
                        connections[prev_node_id] = {}
                    connections[prev_node_id]["main"] = [[{"node": new_node_id, "type": "main", "index": 0}]]
            elif len(nodes) > 1:
                # Connect to the second-to-last node (since we just added one)
                prev_node = nodes[-2]
                prev_node_id = prev_node["id"]
                if prev_node_id not in connections:
                    connections[prev_node_id] = {}
                connections[prev_node_id]["main"] = [[{"node": new_node_id, "type": "main", "index": 0}]]

            # Update workflow data
            workflow_data["n8n_workflow_data"] = n8n_workflow
            workflow_data["_modified"] = True

            # Validate connections after adding node
            validate_and_fix_connections(workflow_data)

            return {
                "success": True,
                "message": f"Added node '{node_name}' with ID {new_node_id}",
                "node_id": new_node_id
            }

        elif function_name == "modify_node":
            # Modify an existing node
            n8n_workflow = workflow_data.get("n8n_workflow_data", {})
            if not n8n_workflow or "nodes" not in n8n_workflow:
                return {"error": "No valid workflow data found"}

            node_identifier = arguments.get("node_identifier")
            updates = arguments.get("updates", {})
            new_name = arguments.get("new_name")

            # Validate arguments
            if not node_identifier:
                return {"error": "node_identifier is required. Use the exact node name from get_workflow_structure."}
            if not updates and not new_name:
                return {"error": "Either updates or new_name is required."}

            # Find the node
            nodes = n8n_workflow["nodes"]
            target_node = next((n for n in nodes if n["name"] == node_identifier or n["id"] == node_identifier), None)

            if not target_node:
                return {"error": f"Node '{node_identifier}' not found"}

            old_name = target_node['name']
            old_id = target_node['id']

            # Update node name if provided
            if new_name:
                target_node["name"] = new_name

                # CRITICAL: Update all connection references that use the old name
                connections = n8n_workflow.get("connections", {})

                # Update source connections (keys in connections object)
                if old_name in connections:
                    connections[new_name] = connections.pop(old_name)

                # Update target connections (node references inside connection objects)
                for source_key, connection_data in connections.items():
                    for connection_type, connection_groups in connection_data.items():
                        for connection_group in connection_groups:
                            for conn in connection_group:
                                if conn.get("node") == old_name:
                                    conn["node"] = new_name

            # Update parameters if provided
            if updates:
                # Deep update parameters - replace specific fields rather than shallow merge
                if "parameters" not in target_node:
                    target_node["parameters"] = {}

                # For each key in updates, directly set it (this replaces the value)
                for key, value in updates.items():
                    target_node["parameters"][key] = value

            workflow_data["_modified"] = True

            # Validate connections after modification
            validate_and_fix_connections(workflow_data)

            response_msg = f"Modified node '{old_name}'"
            if new_name:
                response_msg += f" (renamed to '{new_name}')"

            return {
                "success": True,
                "message": response_msg,
                "updated_parameters": target_node["parameters"] if updates else None,
                "new_name": new_name if new_name else None
            }

        elif function_name == "delete_node":
            # Delete a node
            n8n_workflow = workflow_data.get("n8n_workflow_data", {})
            if not n8n_workflow or "nodes" not in n8n_workflow:
                return {"error": "No valid workflow data found"}

            node_identifier = arguments.get("node_identifier")
            nodes = n8n_workflow["nodes"]

            # Find the node
            target_node = next((n for n in nodes if n["name"] == node_identifier or n["id"] == node_identifier), None)
            if not target_node:
                return {"error": f"Node '{node_identifier}' not found"}

            # Remove node
            nodes.remove(target_node)

            # Clean up connections
            connections = n8n_workflow.get("connections", {})
            node_id = target_node["id"]

            # Remove outgoing connections
            if node_id in connections:
                del connections[node_id]

            # Remove incoming connections
            for conn_source in list(connections.keys()):
                if "main" in connections[conn_source]:
                    for i, conn_list in enumerate(connections[conn_source]["main"]):
                        connections[conn_source]["main"][i] = [
                            c for c in conn_list if c.get("node") != node_id
                        ]

            workflow_data["_modified"] = True

            # Validate connections after deleting node (this will clean up orphaned connections)
            validate_and_fix_connections(workflow_data)

            return {
                "success": True,
                "message": f"Deleted node '{target_node['name']}'"
            }

        elif function_name == "get_workflow_connections":

            n8n_workflow = workflow_data.get("n8n_workflow_data", {})
            if not n8n_workflow or "nodes" not in n8n_workflow:
                return {"error": "No valid workflow data found"}

            nodes = n8n_workflow["nodes"]
            connections = n8n_workflow.get("connections", {})

            id_to_name = {node["id"]: node["name"] for node in nodes}
            name_to_id = {node["name"]: node["id"] for node in nodes}

            connection_list = []
            connected_node_ids = set()

            for source_key, connection_data in connections.items():
                # Determine if source_key is an ID or a name
                if source_key in id_to_name:
                    # It's an ID
                    source_id = source_key
                    source_name = id_to_name[source_key]
                elif source_key in name_to_id:
                    # It's a name (unusual but happens)
                    source_name = source_key
                    source_id = name_to_id[source_key]
                else:
                    continue

                for connection_type, connection_groups in connection_data.items():
                    for connection_group in connection_groups:
                        for conn in connection_group:
                            target_key = conn.get("node")

                            # Determine if target_key is an ID or a name
                            if target_key in id_to_name:
                                target_id = target_key
                                target_name = id_to_name[target_key]
                            elif target_key in name_to_id:
                                target_name = target_key
                                target_id = name_to_id[target_key]
                            else:
                                continue

                            connection_list.append({
                                "from": source_name,
                                "to": target_name,
                                "type": connection_type
                            })

                            # Always add the actual node IDs
                            connected_node_ids.add(source_id)
                            connected_node_ids.add(target_id)

            all_node_ids = {node["id"] for node in nodes}
            disconnected_node_ids = all_node_ids - connected_node_ids
            disconnected_nodes = [id_to_name.get(nid, nid) for nid in disconnected_node_ids]

            # Additional info: show which nodes reference non-existent targets
            broken_connections = []
            for conn in connection_list:
                if conn["to"] not in [n["name"] for n in nodes]:
                    broken_connections.append(f"{conn['from']} → {conn['to']} (target node doesn't exist)")

            return {
                "success": True,
                "total_nodes": len(nodes),
                "total_connections": len(connection_list),
                "connections": connection_list,
                "disconnected_nodes": disconnected_nodes,
                "all_nodes": [node["name"] for node in nodes],
                "broken_connections": broken_connections if broken_connections else []
            }

        elif function_name == "rebuild_workflow_connections":
            # Clear all connections and rebuild sequentially
            n8n_workflow = workflow_data.get("n8n_workflow_data", {})
            if not n8n_workflow or "nodes" not in n8n_workflow:
                return {"error": "No valid workflow data found"}

            nodes = n8n_workflow["nodes"]
            if len(nodes) == 0:
                return {"error": "No nodes to connect"}

            print(f"   🔧 Rebuilding connections for {len(nodes)} nodes:")
            for i, node in enumerate(nodes):
                print(f"      Node {i}: name='{node.get('name')}', id={node.get('id')}, type={type(node.get('id'))}")

            # Clear all existing connections
            n8n_workflow["connections"] = {}

            # Connect nodes sequentially (node 0 → 1 → 2 → ...)
            # Use NODE NAMES for both source and target (consistent format)
            for i in range(len(nodes) - 1):
                source_node = nodes[i]
                target_node = nodes[i + 1]

                source_name = source_node["name"]
                target_name = target_node["name"]

                print(f"      Creating connection: {source_name} → {target_name}")

                # Create connection using NAME as key and NAME as target
                if source_name not in n8n_workflow["connections"]:
                    n8n_workflow["connections"][source_name] = {}

                n8n_workflow["connections"][source_name]["main"] = [[{
                    "node": target_name,  # Use NAME not ID
                    "type": "main",
                    "index": 0
                }]]

            workflow_data["_modified"] = True

            print(f"   📋 Final connections object:")
            print(f"      Keys: {list(n8n_workflow['connections'].keys())}")
            print(f"      Key types: {[type(k) for k in n8n_workflow['connections'].keys()]}")
            print(f"      Full connections: {json.dumps(n8n_workflow['connections'], indent=2)}")

            return {
                "success": True,
                "message": f"Rebuilt {len(nodes) - 1} connections between {len(nodes)} nodes",
                "connections_created": len(nodes) - 1
            }

        elif function_name == "connect_nodes":
            n8n_workflow = workflow_data.get("n8n_workflow_data", {})
            if not n8n_workflow or "nodes" not in n8n_workflow:
                return {"error": "No valid workflow data found"}

            source_node_identifier = arguments.get("source_node")
            target_node_identifier = arguments.get("target_node")
            source_output = arguments.get("source_output", "main")
            target_input_index = arguments.get("target_input_index", 0)

            nodes = n8n_workflow["nodes"]
            connections = n8n_workflow.get("connections", {})

            source_node = next((n for n in nodes if n["name"] == source_node_identifier or n["id"] == source_node_identifier), None)
            target_node = next((n for n in nodes if n["name"] == target_node_identifier or n["id"] == target_node_identifier), None)

            if not source_node:
                return {"error": f"Source node '{source_node_identifier}' not found"}
            if not target_node:
                return {"error": f"Target node '{target_node_identifier}' not found"}

            source_id = source_node["id"]
            target_id = target_node["id"]

            if source_id not in connections:
                connections[source_id] = {}

            if source_output not in connections[source_id]:
                connections[source_id][source_output] = [[]]

            existing_conn = any(
                conn.get("node") == target_id
                for group in connections[source_id][source_output]
                for conn in group
            )

            if existing_conn:
                return {
                    "success": True,
                    "message": f"Connection already exists: {source_node['name']} → {target_node['name']}"
                }

            connection_obj = {
                "node": target_id,
                "type": source_output,
                "index": target_input_index
            }

            # Add to first group (or create new group if needed)
            if connections[source_id][source_output]:
                connections[source_id][source_output][0].append(connection_obj)
            else:
                connections[source_id][source_output] = [[connection_obj]]

            workflow_data["_modified"] = True

            return {
                "success": True,
                "message": f"Connected {source_node['name']} → {target_node['name']}"
            }

        else:
            return {"error": f"Function {function_name} not implemented"}

    except Exception as e:
        return {"success": False, "error": str(e)}


@router.post("/workflow-edit-chat")
async def workflow_edit_chat(
    request: WorkflowEditChatRequest,
    current_user: dict = Depends(require_auth)
):
    """
    Chat interface for editing existing workflows.

    The LLM can add, modify, or delete nodes in the workflow based on user requests.
    """
    try:
        user_id = current_user["user_id"]

        # Get workflow
        result = supabase.table("workflows").select("*").eq("id", request.workflow_id).execute()
        if not result.data or len(result.data) == 0:
            raise HTTPException(status_code=404, detail="Workflow not found")

        workflow = result.data[0]

        # FETCH DIRECTLY FROM N8N to get current state (not stale database data)
        n8n_workflow_data = None
        if workflow.get("n8n_workflow_id"):
            import requests
            N8N_API_KEY = os.getenv("N8N_API_KEY", "your-api-key")
            N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")

            headers = {
                "X-N8N-API-KEY": N8N_API_KEY,
                "Content-Type": "application/json",
            }

            url = f"{N8N_BASE_URL.rstrip('/')}/workflows/{workflow['n8n_workflow_id']}"

            print(f"🔍 Fetching workflow from n8n: {workflow['n8n_workflow_id']}")

            try:
                n8n_response = requests.get(url, headers=headers, timeout=10)
                if n8n_response.status_code == 200:
                    n8n_workflow_data = n8n_response.json()
                    print(f"   ✅ Fetched from n8n successfully")
                    print(f"   Nodes: {len(n8n_workflow_data.get('nodes', []))}")
                    print(f"   Connections: {json.dumps(n8n_workflow_data.get('connections', {}))[:200]}")
                else:
                    print(f"   ⚠️ n8n returned {n8n_response.status_code}, falling back to database")
            except Exception as e:
                print(f"   ⚠️ Error fetching from n8n: {str(e)}, falling back to database")

        # Fallback to database if n8n fetch failed
        if not n8n_workflow_data:
            print(f"   📀 Using workflow data from database")
            n8n_workflow_data = workflow.get("n8n_workflow_data", {})
            if isinstance(n8n_workflow_data, str):
                n8n_workflow_data = json.loads(n8n_workflow_data)

        # Create a mutable workflow data object to track changes
        workflow_data = {
            "n8n_workflow_data": n8n_workflow_data,
            "_modified": False
        }

        # Build system prompt
        system_prompt = f"""You are a workflow editing assistant. You help users modify their n8n automation workflows.

CURRENT WORKFLOW:
Name: {workflow.get("name", "Untitled")}
Status: {workflow.get("status", "unknown")}

YOUR CAPABILITIES:
1. **get_workflow_structure** - View the current workflow nodes and structure
2. **get_workflow_connections** - See how nodes are connected and identify disconnected nodes
3. **add_node** - Add new nodes to the workflow (e.g., HTTP requests, code execution, data transformation)
4. **modify_node** - Change parameters of existing nodes or rename them
5. **connect_nodes** - Connect two nodes together (source → target)
6. **rebuild_workflow_connections** - Clear all connections and rebuild them sequentially (use when connections are broken or out of sync)
7. **delete_node** - Remove nodes from the workflow

⚠️ CRITICAL - AUTONOMOUS WORKFLOW EXECUTION:
1. DO NOT explain what you will do - JUST DO IT with function calls
2. DO NOT show code examples or explain steps - EXECUTE the functions
3. DO NOT say "I'll do X" or "Let's proceed" - CALL THE FUNCTIONS IMMEDIATELY
4. Changes are automatically saved - never mention saving
5. Only call get_workflow_structure ONCE per conversation
6. Response format: ONLY give a brief confirmation or ask a clarifying question

RESPONSE STYLE - BE EXTREMELY CONCISE:
❌ BAD: "To change the node, I'll perform the following: 1. Modify the URL 2. Rename it 3. Check connections..."
✅ GOOD: [calls modify_node] "Done. Changed to send endpoint."

❌ BAD: "I've updated the node to send emails. The node has been renamed to 'Send Email'. All connections are maintained."
✅ GOOD: "Changed to send emails."

❌ BAD: "Let me check the workflow structure first..." [explains steps]
✅ GOOD: [calls get_workflow_structure, then modify_node] "Updated."

ONLY respond with:
- Brief confirmation: "Done." / "Changed to X." / "Added node."
- Clarifying question: "Which node?" / "Connect to which step?"
- Never explain your process or show code examples

COMMON NODE TYPES:
- httpRequest: Make API calls to backend or external services
- code: Execute JavaScript code to transform data
- set: Set specific field values
- if: Conditional branching
- splitInBatches: Process array items one by one

HTTP REQUEST NODE PARAMETERS:
For Google Sheets/Gmail:
{{
    "method": "POST",
    "url": "http://127.0.0.1:8000/tools/gsuite/sheets/read",
    "authentication": "none",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{{{ JSON.stringify({{{{ user_id: '{user_id}', params: {{{{ spreadsheet_id: 'id', range: 'A1:B10' }}}} }}}}) }}}}"
}}

For LLM Processing:
{{
    "method": "POST",
    "url": "http://127.0.0.1:8000/llm-process",
    "authentication": "none",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "={{{{ JSON.stringify({{{{ prompt: 'Your prompt here', input_data: $input.all(), model: 'gpt-4o-mini', temperature: 0.7 }}}}) }}}}"
}}

EXAMPLE INTERACTION 1:
User: "Add a node that reads the google sheet"
You: [call add_node]
Response: "Added."

EXAMPLE INTERACTION 2:
User: "Change the last node from drafting to sending the email"
You: [call get_workflow_structure, call modify_node]
Response: "Changed to send."

EXAMPLE INTERACTION 3:
User: "Make sure all nodes are connected"
You: [call get_workflow_connections, call rebuild_workflow_connections if needed]
Response: "Connected all nodes." OR "Already connected."

EXAMPLE INTERACTION 4:
User: "The nodes aren't connected in n8n"
You: [call rebuild_workflow_connections]
Response: "Rebuilt connections and synced to n8n."

CRITICAL - How to use modify_node:
- node_identifier: Use the EXACT node name from get_workflow_structure (e.g., "Process Sheet Data", "Read Contacts from Google Sheet")
- updates: An object with the parameter keys you want to change
  - For code nodes: {{"jsCode": "your new javascript code"}}
  - For HTTP nodes: {{"url": "new url", "jsonBody": "new body"}}
  - For any parameter: {{"paramName": "new value"}}
- new_name: (Optional but RECOMMENDED) To rename the node, e.g., "new_name": "Process All Sheet Data"

⚠️ IMPORTANT - When to rename nodes:
- If you change a node's functionality (e.g., "send email" → "draft email"), ALWAYS update the name too
- Example: Changing "/gmail/message/send" to "/gmail/message/draft" → Also rename "Send Email" to "Draft Email"
- This keeps the workflow clear and prevents confusion

Examples:
- Change code only: modify_node({{"node_identifier": "Process Sheet Data", "updates": {{"jsCode": "new code"}}}})
- Rename only: modify_node({{"node_identifier": "Process Sheet Data", "new_name": "Process All Data"}})
- Change functionality (BEST PRACTICE): modify_node({{"node_identifier": "Send Email", "updates": {{"url": "http://127.0.0.1:8000/tools/gsuite/gmail/message/draft"}}, "new_name": "Draft Email"}})

CRITICAL - How to check and fix connections:
When user asks to "make sure all nodes are connected" or "connect all nodes":
1. Call get_workflow_connections to see current connections
2. The response shows:
   - connections: list of {{from: "Node A", to: "Node B"}}
   - disconnected_nodes: list of node names that aren't connected
   - all_nodes: complete list of nodes
3. If connections are empty or nodes are disconnected, use rebuild_workflow_connections to rebuild all connections sequentially
4. If only specific nodes need connecting, use connect_nodes({{"source_node": "Read Sheet", "target_node": "Process Data"}})
5. **IMPORTANT**: rebuild_workflow_connections forces a sync to n8n, use it when connections seem broken

CRITICAL - WHAT NOT TO DO:
❌ Show code examples like "modify_node({...})" - CALL THE ACTUAL FUNCTION
❌ Explain steps: "I'll perform the following: 1. X 2. Y" - JUST EXECUTE
❌ Say "Let's proceed" or "Here are the changes executed:" - NO PREAMBLE
❌ Call get_workflow_structure more than ONCE per conversation
❌ Ask "should I proceed?" - they already told you what to do
❌ Mention saving - it's automatic

✅ WHAT TO DO:
✅ Immediately call functions with NO explanation before or after
✅ Multiple function calls in ONE response with NO text between them
✅ ONLY text AFTER all functions execute: brief confirmation
✅ Response pattern: [function1][function2][function3] "Done."
"""

        # Build messages
        messages = [{"role": "system", "content": system_prompt}]

        # Add conversation history
        for msg in request.conversation_history:
            messages.append({"role": msg.role, "content": msg.content})

        # Check if user is saying "ok" or "go ahead" repeatedly - add a strong hint
        user_message = request.message
        if request.message.lower().strip() in ['ok', 'okay', 'go ahead', 'yes', 'do it', 'proceed']:
            # Count how many times they've said this
            ok_count = sum(1 for msg in request.conversation_history
                          if msg.role == 'user' and msg.content.lower().strip() in ['ok', 'okay', 'go ahead', 'yes', 'do it', 'proceed'])

            if ok_count >= 1:
                # They've said ok multiple times - be very explicit
                user_message = f"{request.message}\n\n[SYSTEM OVERRIDE: User has confirmed {ok_count + 1} times. STOP analyzing and EXECUTE the changes NOW using modify_node, add_node, or delete_node, then call save_workflow_changes. DO NOT call get_workflow_structure again.]"

        # Add user's new message
        messages.append({"role": "user", "content": user_message})

        # Keep track of all function calls made during this conversation turn
        all_function_calls = []
        max_iterations = 10  # Prevent infinite loops
        iteration = 0

        # Loop until LLM stops calling functions or we hit max iterations
        while iteration < max_iterations:
            iteration += 1

            print(f"\n🔄 LLM Iteration {iteration}")

            # Call LLM with function calling enabled
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                tools=get_workflow_edit_function_definitions(),
                tool_choice="auto",
                temperature=0.3
            )

            assistant_message = response.choices[0].message

            # Check if LLM wants to call functions
            if assistant_message.tool_calls:
                print(f"📞 LLM calling {len(assistant_message.tool_calls)} function(s)")

                # Add assistant message to conversation
                messages.append(assistant_message)

                # Execute all function calls
                for tool_call in assistant_message.tool_calls:
                    function_name = tool_call.function.name
                    arguments = json.loads(tool_call.function.arguments)

                    print(f"   → {function_name}({json.dumps(arguments)})")

                    # Track this function call
                    all_function_calls.append({
                        "name": function_name,
                        "arguments": arguments
                    })

                    # Execute the function
                    result = await call_workflow_edit_function(
                        function_name, arguments, user_id, workflow_data
                    )

                    print(f"   ✓ Result: {json.dumps(result)[:200]}")

                    # Add function result to conversation
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": function_name,
                        "content": json.dumps(result)
                    })

                # Continue loop - LLM will see function results and decide next action
            else:
                # No more function calls - LLM has generated final text response
                final_message = assistant_message.content
                print(f"💬 Final message: {final_message}")
                break
        else:
            # Hit max iterations - force a response
            final_message = "Completed. (Note: Maximum iteration limit reached)"

        # Auto-save: Save to database if workflow was modified
        if workflow_data.get("_modified"):
            print(f"\n💾 Auto-save: Workflow was modified")
            print(f"   Connections: {json.dumps(workflow_data['n8n_workflow_data'].get('connections', {}))[:200]}")

            # Update n8n workflow
            if workflow.get("n8n_workflow_id"):
                import requests
                N8N_API_KEY = os.getenv("N8N_API_KEY", "your-api-key")
                N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")

                headers = {
                    "X-N8N-API-KEY": N8N_API_KEY,
                    "Content-Type": "application/json",
                }

                # Update existing workflow
                url = f"{N8N_BASE_URL.rstrip('/')}/workflows/{workflow['n8n_workflow_id']}"

                print(f"   📤 Updating n8n workflow {workflow['n8n_workflow_id']}")

                # Only send fields that n8n accepts for updates (filter out read-only fields)
                n8n_update_payload = {
                    "name": workflow_data["n8n_workflow_data"].get("name"),
                    "nodes": workflow_data["n8n_workflow_data"].get("nodes"),
                    "connections": workflow_data["n8n_workflow_data"].get("connections"),
                    "settings": workflow_data["n8n_workflow_data"].get("settings", {}),
                    "staticData": workflow_data["n8n_workflow_data"].get("staticData"),
                }

                # Remove None values
                n8n_update_payload = {k: v for k, v in n8n_update_payload.items() if v is not None}

                print(f"   Sending fields: {list(n8n_update_payload.keys())}")

                try:
                    update_response = requests.put(
                        url,
                        headers=headers,
                        json=n8n_update_payload,
                        timeout=10
                    )
                    print(f"   ✅ n8n response: {update_response.status_code}")
                    if update_response.status_code != 200:
                        print(f"   ❌ n8n error: {update_response.text}")
                    else:
                        print(f"   ✅ n8n workflow updated successfully!")
                except Exception as e:
                    print(f"   ❌ Error: {str(e)}")

            # Update database
            print(f"   📀 Updating database")
            supabase.table("workflows").update({
                "n8n_workflow_data": workflow_data["n8n_workflow_data"]
            }).eq("id", request.workflow_id).execute()
            print(f"   ✅ Database updated")
        else:
            print(f"\n📭 No changes made (_modified = False)")

        print(f"\n📤 Returning to frontend:")
        print(f"   Message: {final_message}")
        print(f"   Function calls: {len(all_function_calls)}")
        print(f"   Workflow modified: {workflow_data.get('_modified', False)}")

        return {
            "message": final_message,
            "function_calls": all_function_calls,
            "workflow_modified": workflow_data.get("_modified", False)
        }

    except Exception as e:
        print(f"Error in workflow edit chat: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
