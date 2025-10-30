"""Google API service for interacting with Sheets and Gmail."""

from typing import Dict, Any, List, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2.credentials import Credentials
from services.oauth_service import get_valid_credentials


def get_sheets_service(user_id: str):
    """Get Google Sheets API service."""
    credentials = get_valid_credentials(user_id)
    if not credentials:
        raise Exception("No valid Google credentials found. Please re-authenticate.")

    return build('sheets', 'v4', credentials=credentials)


def get_gmail_service(user_id: str):
    """Get Gmail API service."""
    credentials = get_valid_credentials(user_id)
    if not credentials:
        raise Exception("No valid Google credentials found. Please re-authenticate.")

    return build('gmail', 'v1', credentials=credentials)


# ============================================================================
# GOOGLE SHEETS OPERATIONS
# ============================================================================

def read_sheet_range(user_id: str, spreadsheet_id: str, range_notation: str) -> Dict[str, Any]:
    """Read data from a Google Sheets range."""
    try:
        service = get_sheets_service(user_id)

        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=range_notation
        ).execute()

        values = result.get('values', [])

        return {
            "values": values,
            "range": result.get('range'),
            "majorDimension": result.get('majorDimension', 'ROWS')
        }

    except HttpError as error:
        raise Exception(f"Google Sheets API error: {error}")
    except Exception as e:
        raise Exception(f"Error reading sheet: {str(e)}")


def write_sheet_range(user_id: str, spreadsheet_id: str, range_notation: str, values: List[List[Any]]) -> Dict[str, Any]:
    """Write data to a Google Sheets range."""
    try:
        service = get_sheets_service(user_id)

        body = {
            'values': values
        }

        result = service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            valueInputOption='RAW',
            body=body
        ).execute()

        return {
            "updatedCells": result.get('updatedCells'),
            "updatedRows": result.get('updatedRows'),
            "updatedColumns": result.get('updatedColumns'),
            "updatedRange": result.get('updatedRange')
        }

    except HttpError as error:
        raise Exception(f"Google Sheets API error: {error}")
    except Exception as e:
        raise Exception(f"Error writing to sheet: {str(e)}")


def append_sheet_data(user_id: str, spreadsheet_id: str, range_notation: str, values: List[List[Any]]) -> Dict[str, Any]:
    """Append data to a Google Sheet."""
    try:
        service = get_sheets_service(user_id)

        body = {
            'values': values
        }

        result = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()

        return {
            "updates": result.get('updates', {}),
            "updatedCells": result['updates'].get('updatedCells') if 'updates' in result else 0,
            "updatedRows": result['updates'].get('updatedRows') if 'updates' in result else 0
        }

    except HttpError as error:
        raise Exception(f"Google Sheets API error: {error}")
    except Exception as e:
        raise Exception(f"Error appending to sheet: {str(e)}")


def create_spreadsheet(user_id: str, title: str, sheet_titles: Optional[List[str]] = None) -> Dict[str, Any]:
    """Create a new Google Spreadsheet."""
    try:
        service = get_sheets_service(user_id)

        spreadsheet_body = {
            'properties': {
                'title': title
            }
        }

        if sheet_titles:
            spreadsheet_body['sheets'] = [
                {'properties': {'title': sheet_title}} for sheet_title in sheet_titles
            ]

        spreadsheet = service.spreadsheets().create(body=spreadsheet_body).execute()

        return {
            "spreadsheet_id": spreadsheet.get('spreadsheetId'),
            "spreadsheet_url": spreadsheet.get('spreadsheetUrl'),
            "title": spreadsheet['properties'].get('title')
        }

    except HttpError as error:
        raise Exception(f"Google Sheets API error: {error}")
    except Exception as e:
        raise Exception(f"Error creating spreadsheet: {str(e)}")


def clear_sheet_range(user_id: str, spreadsheet_id: str, range_notation: str) -> Dict[str, Any]:
    """Clear a range in Google Sheets."""
    try:
        service = get_sheets_service(user_id)

        result = service.spreadsheets().values().clear(
            spreadsheetId=spreadsheet_id,
            range=range_notation,
            body={}
        ).execute()

        return {
            "clearedRange": result.get('clearedRange')
        }

    except HttpError as error:
        raise Exception(f"Google Sheets API error: {error}")
    except Exception as e:
        raise Exception(f"Error clearing sheet: {str(e)}")


# ============================================================================
# GMAIL OPERATIONS
# ============================================================================

def create_message_payload(to: str = "", cc: str = "", bcc: str = "", subject: str = "", body: str = "") -> Dict[str, Any]:
    """Create email message payload."""
    import base64
    from email.mime.text import MIMEText

    message = MIMEText(body)
    message['to'] = to
    if cc:
        message['cc'] = cc
    if bcc:
        message['bcc'] = bcc
    message['subject'] = subject

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode('utf-8')

    return {'raw': raw_message}


def create_gmail_draft(user_id: str, to: str = "", cc: str = "", bcc: str = "", subject: str = "", body: str = "") -> Dict[str, Any]:
    """Create a Gmail draft."""
    try:
        service = get_gmail_service(user_id)

        message_payload = create_message_payload(to, cc, bcc, subject, body)

        draft = service.users().drafts().create(
            userId='me',
            body={'message': message_payload}
        ).execute()

        return {
            "draft_id": draft.get('id'),
            "message": {
                "id": draft['message'].get('id'),
                "threadId": draft['message'].get('threadId')
            },
            "to": to,
            "cc": cc,
            "bcc": bcc,
            "subject": subject
        }

    except HttpError as error:
        raise Exception(f"Gmail API error: {error}")
    except Exception as e:
        raise Exception(f"Error creating draft: {str(e)}")


def send_gmail_message(user_id: str, to: str = "", cc: str = "", bcc: str = "", subject: str = "", body: str = "") -> Dict[str, Any]:
    """Send an email via Gmail."""
    try:
        service = get_gmail_service(user_id)

        message_payload = create_message_payload(to, cc, bcc, subject, body)

        sent_message = service.users().messages().send(
            userId='me',
            body=message_payload
        ).execute()

        return {
            "message_id": sent_message.get('id'),
            "thread_id": sent_message.get('threadId'),
            "label_ids": sent_message.get('labelIds', []),
            "to": to,
            "cc": cc,
            "subject": subject,
            "status": "sent"
        }

    except HttpError as error:
        raise Exception(f"Gmail API error: {error}")
    except Exception as e:
        raise Exception(f"Error sending email: {str(e)}")


def list_gmail_messages(user_id: str, query: str = "", max_results: int = 10, label_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """List Gmail messages with optional filters."""
    try:
        service = get_gmail_service(user_id)

        params = {
            'userId': 'me',
            'maxResults': max_results
        }

        if query:
            params['q'] = query
        if label_ids:
            params['labelIds'] = label_ids

        results = service.users().messages().list(**params).execute()

        messages = results.get('messages', [])

        return {
            "messages": messages,
            "resultSizeEstimate": results.get('resultSizeEstimate', 0),
            "nextPageToken": results.get('nextPageToken')
        }

    except HttpError as error:
        raise Exception(f"Gmail API error: {error}")
    except Exception as e:
        raise Exception(f"Error listing messages: {str(e)}")
