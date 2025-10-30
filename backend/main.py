from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from lib.video_processor import process_video_from_s3
from lib.step_generator import generate_steps
import os
import boto3
from botocore.exceptions import ClientError
import time
from dotenv import load_dotenv
from lib.workflow_builder import create_workflow
from routes.tools import gsuite, gmail
from routes import auth, workflows
from middleware.auth import require_auth
from typing import Dict
from services import workflow_service

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
app.include_router(gsuite.router, prefix="/tools/gsuite", tags=["Google Sheets Tools"])
app.include_router(gmail.router, prefix="/tools/gmail", tags=["Gmail Tools"])

N8N_API_KEY = os.getenv("N8N_API_KEY", "your-api-key")
N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678/api/v1")

class VideoRequest(BaseModel):
    key: str
    interval_seconds: int = 3

class UploadUrlRequest(BaseModel):
    fileName: str
    fileType: str

@app.post("/upload-url")
async def get_upload_url(req: UploadUrlRequest):
    """Generate a presigned URL for uploading a file to S3"""
    try:
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
        key = f"uploads/{timestamp}-{req.fileName}"

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

        print("Creating n8n workflow...")

        # Generate n8n workflow from steps
        print("Creating n8n workflow from generated steps...")
        workflow_result = create_workflow(
            steps=steps,
            workflow_name=f"Video Workflow - {req.key}",
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

        # Add workflow information to the result
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

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
