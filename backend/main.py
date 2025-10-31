from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from lib.video_processor import process_video_from_s3
from lib.step_generator import generate_steps
import os
import boto3
from botocore.exceptions import ClientError
import time
import requests
from dotenv import load_dotenv
from lib.workflow_builder import create_workflow
from lib.workflow_planner import interactive_workflow_planning, gather_user_responses, enrich_steps_with_data, generate_n8n_workflow_with_complete_info
from routes.tools.gsuite import sheets, gmail
from routes import auth, workflows, videos
from middleware.auth import require_auth
from typing import Dict, Optional, Any, List
from services import workflow_service, video_service


load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:3002"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(workflows.router, prefix="/workflows", tags=["Workflows"])
app.include_router(videos.router, prefix="/videos", tags=["Videos"])
app.include_router(sheets.router, prefix="/tools/gsuite/sheets", tags=["Google Sheets Tools"])
app.include_router(gmail.router, prefix="/tools/gsuite/gmail", tags=["Gmail Tools"])

N8N_API_KEY = os.getenv("N8N_API_KEY", "your-api-key")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")

class VideoRequest(BaseModel):
    key: str
    interval_seconds: int = 3

class UploadUrlRequest(BaseModel):
    fileName: str
    fileType: str

class WorkflowQuestionsResponse(BaseModel):
    user_responses: Dict[str, str]
    workflow_draft_id: str

@app.post("/upload-url")
async def get_upload_url(req: UploadUrlRequest, user: Dict = Depends(require_auth)):
    """Generate a presigned URL for uploading a file to S3"""
    try:
        user_id = user["user_id"]
        bucket = os.getenv("AWS_S3_BUCKET")
        region = os.getenv("AWS_REGION")
        aws_key = os.getenv("AWS_ACCESS_KEY_ID")
        aws_secret = os.getenv("AWS_SECRET_ACCESS_KEY")

        if not bucket:
            raise ValueError("AWS_S3_BUCKET environment variable not set")
        if not region:
            raise ValueError("AWS_REGION environment variable not set")
        if not aws_key:
            raise ValueError("AWS_ACCESS_KEY_ID environment variable not set")
        if not aws_secret:
            raise ValueError("AWS_SECRET_ACCESS_KEY environment variable not set")

        s3_client = boto3.client(
            's3',
            region_name=region,
            aws_access_key_id=aws_key,
            aws_secret_access_key=aws_secret
        )

        timestamp = int(time.time() * 1000)
        key = f"uploads/{user_id}/{timestamp}-{req.fileName}"

        presigned_url = s3_client.generate_presigned_url(
            'put_object',
            Params={
                'Bucket': bucket,
                'Key': key,
                'ContentType': req.fileType
            },
            ExpiresIn=3600  # Increased to 1 hour for large video uploads
        )

        return {"url": presigned_url, "key": key}

    except ClientError as e:
        raise HTTPException(status_code=500, detail=f"AWS Error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test-workflow")
async def test_workflow():
    """Test endpoint to generate a sample workflow that calls our backend"""
    sample_steps = [
        {
            "action": "Read email addresses from Google Sheets",
            "service": "googleSheets",
            "operation": "readRange",
            "parameters": {
                "spreadsheet_id": "sample_sheet_123",
                "range": "B2:B10"
            }
        },
        {
            "action": "Create Gmail draft with CC recipients",
            "service": "gmail",
            "operation": "createDraft",
            "parameters": {
                "to": "",
                "cc": "{{emails_from_sheet}}",
                "subject": "Weekly Report",
                "body": "Please find the weekly report attached."
            }
        }
    ]

    try:
        workflow_result = create_workflow(
            steps=sample_steps,
            workflow_name="Test Backend Integration Workflow",
            user_id="test_user_123"
        )
        return {
            "message": "Sample workflow generated successfully",
            "workflow": workflow_result.get("workflow"),
            "instructions": "Import this workflow JSON into n8n to see HTTP requests to our backend"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-video")
async def process_video(req: VideoRequest, user: Dict = Depends(require_auth)):
    try:
        user_id = user["user_id"]
        bucket = os.getenv("AWS_S3_BUCKET")
        if not bucket:
            raise ValueError("AWS_S3_BUCKET environment variable not set")

        print(f"Processing video for user {user_id}...")

        # Process video and extract frames
        result = process_video_from_s3(req.key, bucket, req.interval_seconds)

        print("Generating steps from frames...")

        # Generate steps from frames
        steps = generate_steps(result["frames"], len(result["frames"]))
        result["steps"] = steps

        print("Planning workflow with interactive system...")

        # Use interactive workflow planning
        planning_result = interactive_workflow_planning(
            steps=steps,
            workflow_name=f"Video Workflow - {req.key.split('/')[-1]}",
            user_id=user_id
        )

        result["planning"] = planning_result

        if planning_result["status"] == "needs_input":
            # Return questions to user
            result["needs_clarification"] = True
            result["questions"] = planning_result["questions"]
            result["message"] = "Please provide additional information to complete the workflow"

            # Save partial workflow to database
            saved_workflow = workflow_service.create_workflow(
                user_id=user_id,
                name=f"Video Workflow - {req.key.split('/')[-1]} (Pending)",
                steps=steps,
                video_key=req.key,
                description=f"Workflow pending user input from video {req.key}",
                status="draft"
            )
            result["workflow_draft_id"] = saved_workflow.get("id")

        else:
            # Workflow is complete, create in n8n
            print("Creating complete n8n workflow...")
            workflow_result = create_workflow(
                steps=steps,
                workflow_name=f"Video Workflow - {req.key.split('/')[-1]}",
                user_id=user_id
            )

            # Save workflow to database
            print("Saving workflow to database...")
            saved_workflow = workflow_service.create_workflow(
                user_id=user_id,
                name=f"Video Workflow - {req.key.split('/')[-1]}",
                steps=steps,
                video_key=req.key,
                description=f"Auto-generated workflow from video {req.key}",
                n8n_workflow_id=workflow_result.get("workflow_id"),
                n8n_workflow_data=workflow_result.get("workflow")
            )

            result["workflow"] = {
                "status": workflow_result["status"],
                "workflow_id": workflow_result.get("workflow_id"),
                "workflow_url": workflow_result.get("workflow_url"),
                "workflow_structure": workflow_result.get("workflow"),
                "database_id": saved_workflow.get("id")
            }

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze-workflow")
async def analyze_workflow_draft(
    request: dict,
    user: Dict = Depends(require_auth)
):
    """Re-analyze a draft workflow and return questions for missing information."""
    try:
        user_id = user["user_id"]
        workflow_id = request.get("workflow_id")

        if not workflow_id:
            raise HTTPException(status_code=400, detail="workflow_id is required")

        # Get the draft workflow
        draft_workflow = workflow_service.get_workflow_by_id(workflow_id, user_id)

        if not draft_workflow:
            raise HTTPException(status_code=404, detail="Draft workflow not found")

        steps = draft_workflow.get("steps", [])

        # Analyze workflow requirements
        from lib.workflow_planner import analyze_workflow_requirements

        analysis = analyze_workflow_requirements(steps, user_id)

        if analysis["complete"]:
            return {
                "questions": [],
                "complete": True,
                "message": "No additional information needed"
            }
        else:
            return {
                "questions": analysis["missing_info"],
                "complete": False,
                "message": "Please provide the following information"
            }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/enrich-sheet-question")
async def enrich_sheet_question(
    request: dict,
    user: Dict = Depends(require_auth)
):
    """Enrich a sheet column question with actual column data from the spreadsheet."""
    try:
        user_id = user["user_id"]
        spreadsheet_id = request.get("spreadsheet_id")

        if not spreadsheet_id:
            raise HTTPException(status_code=400, detail="spreadsheet_id is required")

        # Directly call the sheet inspection logic instead of making HTTP request to self
        from services.google_api_service import read_sheet_range

        print(f"Enriching sheet question for spreadsheet {spreadsheet_id}, user {user_id}")

        # Read the first row to get headers
        headers_data = read_sheet_range(user_id, spreadsheet_id, "1:1")

        if not headers_data or "values" not in headers_data or not headers_data["values"]:
            return {
                "success": False,
                "error": "Could not read sheet headers. The sheet might be empty."
            }

        headers = headers_data["values"][0] if headers_data["values"] else []

        # Create column mapping (A, B, C, etc. -> header names)
        column_map = {}
        for idx, header in enumerate(headers):
            col_letter = chr(65 + idx)  # A=65 in ASCII
            column_map[col_letter] = header if header else f"Column {col_letter}"

        # Read sample data (next 3 rows after header)
        sample_range = "2:4"
        sample_data_result = read_sheet_range(user_id, spreadsheet_id, sample_range)

        sample_data = []
        if sample_data_result and "values" in sample_data_result:
            for row in sample_data_result["values"]:
                row_data = {}
                for idx, value in enumerate(row):
                    col_letter = chr(65 + idx)
                    row_data[col_letter] = value
                sample_data.append(row_data)

        sheet_data = {
            "spreadsheet_id": spreadsheet_id,
            "headers": column_map,
            "sample_data": sample_data,
            "total_columns": len(headers),
            "sample_row_count": len(sample_data)
        }

        print(f"Sheet data enriched successfully: {len(headers)} columns, {len(sample_data)} sample rows")

        return {
            "success": True,
            "sheet_data": sheet_data
        }

    except Exception as e:
        print(f"Error enriching sheet question: {str(e)}")
        return {
            "success": False,
            "error": f"Failed to inspect sheet: {str(e)}"
        }


class PlanWorkflowRequest(BaseModel):
    steps: List[Dict[str, Any]]
    workflow_name: str
    video_key: Optional[str] = None

@app.post("/plan-workflow")
async def plan_workflow(
    request: PlanWorkflowRequest,
    user: Dict = Depends(require_auth)
):
    """Plan a workflow with confirmed steps - either complete it or ask for clarification."""
    try:
        user_id = user["user_id"]

        print("Planning workflow with confirmed steps...")

        # Use interactive workflow planning
        planning_result = interactive_workflow_planning(
            steps=request.steps,
            workflow_name=request.workflow_name,
            user_id=user_id
        )

        if planning_result["status"] == "needs_input":
            # Return questions to user
            saved_workflow = workflow_service.create_workflow(
                user_id=user_id,
                name=f"{request.workflow_name} (Pending)",
                steps=request.steps,
                video_key=request.video_key,
                description=f"Workflow pending user input",
                status="draft"
            )

            return {
                "needs_clarification": True,
                "questions": planning_result["questions"],
                "workflow_draft_id": saved_workflow.get("id")
            }
        else:
            # Workflow is complete, create in n8n
            print("Creating complete n8n workflow...")
            workflow_result = create_workflow(
                steps=request.steps,
                workflow_name=request.workflow_name,
                user_id=user_id
            )

            # Save workflow to database
            saved_workflow = workflow_service.create_workflow(
                user_id=user_id,
                name=request.workflow_name,
                steps=request.steps,
                video_key=request.video_key,
                description=f"Auto-generated workflow",
                n8n_workflow_id=workflow_result.get("workflow_id"),
                n8n_workflow_data=workflow_result.get("workflow")
            )

            return {
                "needs_clarification": False,
                "workflow": {
                    "status": workflow_result["status"],
                    "workflow_id": workflow_result.get("workflow_id"),
                    "workflow_url": workflow_result.get("workflow_url"),
                    "database_id": saved_workflow.get("id")
                }
            }

    except Exception as e:
        print(f"Error planning workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


class WorkflowModifyRequest(BaseModel):
    current_steps: List[Dict[str, Any]]
    user_request: str

@app.post("/modify-workflow")
async def modify_workflow(
    request: WorkflowModifyRequest,
    user: Dict = Depends(require_auth)
):
    """Modify workflow steps based on user's natural language request."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        current_steps_str = json.dumps(request.current_steps, indent=2)

        prompt = f"""You are a workflow automation expert. The user has a workflow and wants to modify it.

Current Workflow Steps:
{current_steps_str}

User's Request: "{request.user_request}"

Your task:
1. Understand what the user wants to change
2. Modify the workflow steps accordingly
3. Return the updated steps in the SAME format
4. Provide a brief explanation of what you changed

Return a JSON object with this structure:
{{
    "updated_steps": [...],  // Same format as input
    "explanation": "I've updated the workflow to... [explain changes]",
    "changes_made": ["Added step to filter emails", "Changed to send individual emails"]
}}

IMPORTANT:
- Keep the same structure (action, service, operation, parameters)
- If adding steps, be specific about the service and operation
- If removing steps, explain why
- If modifying parameters, preserve existing values where possible"""

        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a workflow modification expert. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=2000
        )

        response_text = response.choices[0].message.content.strip()

        # Remove markdown code blocks if present
        if response_text.startswith("```"):
            response_text = response_text.split("```")[1]
            if response_text.startswith("json"):
                response_text = response_text[4:]
            response_text = response_text.strip()

        result = json.loads(response_text)

        return {
            "updated_steps": result.get("updated_steps", request.current_steps),
            "explanation": result.get("explanation", "I've updated the workflow based on your request."),
            "changes_made": result.get("changes_made", [])
        }

    except Exception as e:
        print(f"Error modifying workflow: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to modify workflow: {str(e)}")


class ChatHelperRequest(BaseModel):
    question: str
    context: Dict[str, Any]

@app.post("/workflow-chat-helper")
async def workflow_chat_helper(
    request: ChatHelperRequest,
    user: Dict = Depends(require_auth)
):
    """Provide LLM assistance for filling out workflow questions."""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        # Build context from the workflow questions
        context_str = "User is filling out workflow parameters:\n"
        if "questions" in request.context:
            for q in request.context["questions"]:
                context_str += f"\nStep: {q.get('step_description', '')}\n"
                for field in q.get("missing_fields", []):
                    context_str += f"  - {field.get('question', '')}\n"

        prompt = f"""You are a helpful assistant helping users fill out workflow automation parameters.

{context_str}

User's question: {request.question}

Provide a concise, helpful answer. If the user is asking about:
- Spreadsheet IDs: Explain they can find it in the Google Sheets URL between /d/ and /edit
- Ranges: Explain Google Sheets range notation (e.g., 'Sheet1!A1:B10')
- Email addresses: Help them understand the format needed
- Any other parameter: Provide clear guidance

Keep your answer brief and actionable."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a helpful workflow automation assistant."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=300
        )

        answer = response.choices[0].message.content

        return {
            "answer": answer
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/complete-workflow")
async def complete_workflow_with_answers(
    request: WorkflowQuestionsResponse,
    user: Dict = Depends(require_auth)
):
    """Complete a workflow by providing answers to clarifying questions."""
    try:
        user_id = user["user_id"]
        workflow_draft_id = request.workflow_draft_id
        user_responses = request.user_responses

        # Get the draft workflow
        draft_workflow = workflow_service.get_workflow_by_id(workflow_draft_id, user_id)

        if not draft_workflow:
            raise HTTPException(status_code=404, detail="Draft workflow not found")

        steps = draft_workflow.get("steps", [])

        # Enrich steps with user responses
        # Convert flat user_responses to step-indexed format
        collected_data = {}
        for key, value in user_responses.items():
            # Parse key format: "step_0_spreadsheet_id" -> step_index: 0, field: spreadsheet_id
            parts = key.split("_", 2)
            if len(parts) >= 3 and parts[0] == "step":
                step_idx = int(parts[1])
                field_name = parts[2]

                if step_idx not in collected_data:
                    collected_data[step_idx] = {}
                collected_data[step_idx][field_name] = value

        # Handle different search modes
        for step_idx, data in collected_data.items():
            search_mode = data.get('search_mode', 'specific_column')

            if search_mode == 'smart_search' and 'data_type' in data:
                # Smart search mode - find all matching data
                print(f"Using smart search for {data.get('data_type')}")

                # Call smart search endpoint
                import requests as req
                try:
                    search_response = req.post(
                        "http://127.0.0.1:8000/tools/gsuite/sheets/smart-search",
                        json={
                            "user_id": user_id,
                            "spreadsheet_id": data.get('spreadsheet_id'),
                            "data_type": data.get('data_type'),
                            "start_row": int(data.get('start_row', 2)),
                            "end_row": int(data.get('end_row')) if data.get('end_row') else None
                        },
                        timeout=15
                    )

                    if search_response.status_code == 200:
                        result = search_response.json()
                        if result.get("success"):
                            search_data = result.get("data", {})
                            # Store the found values
                            data['smart_search_results'] = search_data.get('unique_values', [])
                            data['columns_found'] = search_data.get('columns_with_data', [])

                            # Use first recommended column as range
                            if search_data.get('recommended_columns'):
                                col = search_data['recommended_columns'][0]
                                start = data.get('start_row', '2')
                                end = data.get('end_row', '')
                                data['range'] = f"{col}{start}:{col}{end}" if end else f"{col}{start}:{col}"

                except Exception as e:
                    print(f"Smart search failed: {str(e)}")

                # Clean up temporary fields
                data.pop('search_mode', None)
                data.pop('data_type', None)
                data.pop('start_row', None)
                data.pop('end_row', None)

            elif 'column' in data and 'start_row' in data:
                # Specific column mode
                col = data['column']
                start = data.get('start_row', '2')
                end = data.get('end_row', '')

                # Construct range like "C2:C6" or "C2:C" (for all rows)
                if end:
                    range_str = f"{col}{start}:{col}{end}"
                else:
                    range_str = f"{col}{start}:{col}"

                # Replace range and remove individual fields
                data['range'] = range_str
                # Keep column info for reference but remove the temporary fields
                data.pop('start_row', None)
                data.pop('end_row', None)

        enriched_steps = enrich_steps_with_data(steps, collected_data)

        # Generate final workflow with complete information
        print("Generating final n8n workflow with user-provided data...")
        final_workflow = generate_n8n_workflow_with_complete_info(
            steps=enriched_steps,
            workflow_name=draft_workflow.get("name", "").replace(" (Pending)", ""),
            user_id=user_id
        )

        # Create workflow in n8n
        headers = {
            "X-N8N-API-KEY": N8N_API_KEY,
            "Content-Type": "application/json",
        }

        url = N8N_BASE_URL.rstrip("/") + "/workflows"
        print(f"Creating workflow in n8n at: {url}")
        print(f"Workflow data: {final_workflow}")

        try:
            response = requests.post(url, headers=headers, json=final_workflow, timeout=10)
            print(f"n8n response status: {response.status_code}")
            print(f"n8n response body: {response.text}")
        except Exception as n8n_error:
            print(f"Error calling n8n API: {str(n8n_error)}")
            # Continue anyway to save to database
            response = None

        workflow_result = {
            "status": response.status_code if response else 500,
            "body": response.text if response else "Failed to connect to n8n"
        }

        if response and response.status_code == 200:
            n8n_response = response.json()
            workflow_result["workflow_id"] = n8n_response.get("id")
            workflow_result["workflow_url"] = f"http://localhost:5678/workflow/{n8n_response.get('id')}"

        # Update the workflow in database
        workflow_service.update_workflow(
            workflow_draft_id,
            user_id,
            {
                "steps": enriched_steps,
                "n8n_workflow_id": workflow_result.get("workflow_id"),
                "n8n_workflow_data": final_workflow,
                "status": "active",
                "name": draft_workflow.get("name", "").replace(" (Pending)", "")
            }
        )

        return {
            "success": True,
            "message": "Workflow completed successfully",
            "workflow": workflow_result
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
