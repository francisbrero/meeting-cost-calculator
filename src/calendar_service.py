import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Tuple, Optional
from google.cloud import firestore
from google.oauth2 import service_account
from auth import calendar_service
from config import config

# Initialize Firestore with service account credentials
creds = service_account.Credentials.from_service_account_info(
    config.google_credentials_json,
    scopes=['https://www.googleapis.com/auth/datastore']
)
db = firestore.Client(credentials=creds, project=config.google_credentials_json['project_id'])


def user_doc(email: str) -> firestore.DocumentReference:
    """Get Firestore document for storing user sync tokens."""
    return db.collection("meetingcost").document(email)


def list_changed_events(cal, calendar_id: str, sync_token: Optional[str]) -> Tuple[Optional[List[Dict]], Optional[str]]:
    """
    Fetch changed events from Calendar API using sync tokens.
    Returns (events, next_sync_token) or (None, None) if sync token is invalid.
    """
    events = []
    try:
        if sync_token:
            req = cal.events().list(
                calendarId=calendar_id, 
                syncToken=sync_token, 
                maxResults=2500,
                fields="items(attendees,organizer,id,recurringEventId,start,end,description,extendedProperties),nextPageToken,nextSyncToken"
            )
        else:
            now = datetime.now(timezone.utc)
            time_min = (now - timedelta(days=config.window_days)).isoformat()
            time_max = (now + timedelta(days=config.window_days)).isoformat()
            req = cal.events().list(
                calendarId=calendar_id, 
                singleEvents=True, 
                showDeleted=False,
                timeMin=time_min, 
                timeMax=time_max, 
                maxResults=2500,
                fields="items(attendees,organizer,id,recurringEventId,start,end,description,extendedProperties),nextPageToken,nextSyncToken"
            )
        
        while True:
            resp = req.execute()
            events.extend(resp.get("items", []))
            page = resp.get("nextPageToken")
            if page:
                req = cal.events().list_next(req, resp)
            else:
                return events, resp.get("nextSyncToken")
                
    except Exception as e:
        # If sync token is stale, caller should drop it and do a windowed resync
        if "syncToken" in str(e) and "full sync" in str(e).lower():
            return None, None
        raise


def get_cost_display_format(cost: int) -> str:
    """Format cost with color coding using emoji indicators."""
    # Use emoji with single cost display for clean appearance
    if cost > 1000:
        # Red for high cost (>$1000)
        return f"🔴 ${cost:,}"
    elif cost > 500:
        # Orange for medium cost (>$500) 
        return f"🟠 ${cost:,}"
    else:
        # Green for low cost (≤$500)
        return f"🟢 ${cost:,}"


def create_dual_cost_display(cost_info: Dict) -> str:
    """Create display text for invited vs effective costs."""
    invited_cost = cost_info['invited_cost']
    effective_cost = cost_info['effective_cost']
    invited_count = cost_info['invited_count']
    effective_count = cost_info['effective_count']
    
    # If costs are the same (everyone responded yes/maybe), show single cost
    if invited_cost == effective_cost:
        cost_display = get_cost_display_format(effective_cost)
        return f"{config.cost_tag}: {cost_display}"
    
    # Show both costs when they differ
    invited_display = get_cost_display_format(invited_cost)
    effective_display = get_cost_display_format(effective_cost)
    
    return (f"{config.cost_tag}: {effective_display}\n"
            f"└─ Invited cost: {invited_display} "
            f"({invited_count} invited → {effective_count} attending)")


def annotate_event(cal: Any, calendar_id: str, event: Dict[str, Any], cost_info) -> None:
    """Add cost annotation to calendar event description with invited vs effective costs."""
    event_id = event["id"]
    desc = event.get("description", "") or ""
    
    # Handle both old single cost format and new dict format for backward compatibility
    if isinstance(cost_info, int):
        # Legacy single cost format
        cost_display = get_cost_display_format(cost_info)
        cost_line = f"{config.cost_tag}: {cost_display}"
        extended_cost = str(cost_info)
    else:
        # New dual cost format
        cost_line = create_dual_cost_display(cost_info)
        extended_cost = str(cost_info['effective_cost'])
    
    # Check if already annotated (idempotent) - look for the tag pattern
    tag_pattern = re.escape(config.cost_tag) + r":.*?(?=\n(?![└─])|$)"
    if re.search(tag_pattern, desc, re.DOTALL):
        # Replace existing cost annotation (including multi-line invited cost info)
        new_desc = re.sub(tag_pattern, cost_line, desc, flags=re.DOTALL)
    else:
        # Add new cost line at the beginning for visibility
        if desc.strip():
            new_desc = f"{cost_line}\n\n{desc}"
        else:
            new_desc = cost_line
    
    # Update event with cost in description and extended properties
    patch_body = {
        "description": new_desc,
        "extendedProperties": {
            "private": {
                "meetingCost": extended_cost,
                "invitedCost": str(cost_info['invited_cost']) if isinstance(cost_info, dict) else extended_cost,
                "effectiveCost": str(cost_info['effective_cost']) if isinstance(cost_info, dict) else extended_cost
            }
        }
    }
    
    cal.events().patch(
        calendarId=calendar_id,
        eventId=event_id,
        body=patch_body,
        sendNotifications=False  # Don't spam attendees with updates
    ).execute()


def save_sync_token(email: str, sync_token: str) -> None:
    """Save sync token for user in Firestore."""
    user_doc(email).set({"syncToken": sync_token}, merge=True)


def get_sync_token(email: str) -> Optional[str]:
    """Get sync token for user from Firestore."""
    doc = user_doc(email).get()
    return doc.to_dict().get("syncToken") if doc.exists else None