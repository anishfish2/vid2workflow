from fastapi import APIRouter
from models.tools import ToolRequest, ToolResponse
from services.google_api_service import (
    create_gmail_draft,
    send_gmail_message,
    list_gmail_messages
)
from typing import Dict

router = APIRouter()

# Gmail Operations

@router.post("/draft/create")
async def create_email_draft_api(request: ToolRequest):
    """Create a new email draft"""
    try:
        user_id = request.user_id
        to_recipients = request.params.get("to", "")
        cc_recipients = request.params.get("cc", "")
        bcc_recipients = request.params.get("bcc", "")
        subject = request.params.get("subject", "")
        body = request.params.get("body", "")

        # Handle both string and list formats for recipients
        if isinstance(cc_recipients, list):
            cc_recipients = ", ".join(cc_recipients)
        if isinstance(to_recipients, list):
            to_recipients = ", ".join(to_recipients)
        if isinstance(bcc_recipients, list):
            bcc_recipients = ", ".join(bcc_recipients)

        print(f"Creating draft for user {user_id}")
        print(f"To: {to_recipients}, CC: {cc_recipients}, Subject: {subject}")

        data = create_gmail_draft(user_id, to_recipients, cc_recipients, bcc_recipients, subject, body)

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

@router.post("/draft/update")
async def update_email_draft_api(request: ToolRequest):
    """Update an existing email draft"""
    try:
        draft_id = request.params.get("draft_id")
        to_recipients = request.params.get("to", None)
        cc_recipients = request.params.get("cc", None)
        bcc_recipients = request.params.get("bcc", None)
        subject = request.params.get("subject", None)
        body = request.params.get("body", None)

        print(f"Updating draft {draft_id} for user {request.user_id}")

        return ToolResponse(
            success=True,
            data={
                "draft_id": draft_id,
                "updated_fields": {
                    k: v for k, v in {
                        "to": to_recipients,
                        "cc": cc_recipients,
                        "bcc": bcc_recipients,
                        "subject": subject,
                        "body": body
                    }.items() if v is not None
                }
            }
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )

@router.post("/draft/send")
async def send_draft(request: ToolRequest):
    """Send an email draft"""
    try:
        draft_id = request.params.get("draft_id")

        print(f"Sending draft {draft_id} for user {request.user_id}")

        return ToolResponse(
            success=True,
            data={
                "message_id": f"sent_msg_{draft_id}",
                "thread_id": "thread_123",
                "status": "sent"
            }
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )

@router.post("/message/send")
async def send_email_api(request: ToolRequest):
    """Send an email directly without creating a draft"""
    try:
        user_id = request.user_id
        to_recipients = request.params.get("to", "")
        cc_recipients = request.params.get("cc", "")
        bcc_recipients = request.params.get("bcc", "")
        subject = request.params.get("subject", "")
        body = request.params.get("body", "")

        # Handle list formats
        if isinstance(to_recipients, list):
            to_recipients = ", ".join(to_recipients)
        if isinstance(cc_recipients, list):
            cc_recipients = ", ".join(cc_recipients)
        if isinstance(bcc_recipients, list):
            bcc_recipients = ", ".join(bcc_recipients)

        print(f"Sending email for user {user_id}")
        print(f"To: {to_recipients}, CC: {cc_recipients}, Subject: {subject}")

        data = send_gmail_message(user_id, to_recipients, cc_recipients, bcc_recipients, subject, body)

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

@router.post("/message/reply")
async def reply_to_email_api(request: ToolRequest):
    """Reply to an existing email thread"""
    try:
        thread_id = request.params.get("thread_id")
        message_id = request.params.get("message_id")
        body = request.params.get("body", "")
        reply_all = request.params.get("reply_all", False)

        print(f"Replying to thread {thread_id} for user {request.user_id}")

        return ToolResponse(
            success=True,
            data={
                "message_id": f"reply_msg_{message_id}",
                "thread_id": thread_id,
                "status": "sent",
                "reply_to": message_id
            }
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )

@router.post("/message/list")
async def list_messages_api(request: ToolRequest):
    """List messages with optional filters"""
    try:
        user_id = request.user_id
        query = request.params.get("query", "")
        max_results = request.params.get("max_results", 10)
        label_ids = request.params.get("label_ids", None)

        print(f"Listing messages for user {user_id} with query: {query}")

        data = list_gmail_messages(user_id, query, max_results, label_ids)

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

@router.post("/cc/add")
async def add_cc_recipients_api(request: ToolRequest):
    """Add CC recipients to an email or draft"""
    try:
        draft_id = request.params.get("draft_id", None)
        message_id = request.params.get("message_id", None)
        cc_emails = request.params.get("cc_emails", [])

        if isinstance(cc_emails, str):
            cc_emails = [cc_emails]

        print(f"Adding CC recipients for user {request.user_id}: {cc_emails}")

        return ToolResponse(
            success=True,
            data={
                "added_cc": cc_emails,
                "draft_id": draft_id,
                "message_id": message_id
            }
        )
    except Exception as e:
        return ToolResponse(
            success=False,
            error=str(e),
            retryable=True
        )