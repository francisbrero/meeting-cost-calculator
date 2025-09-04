import time
from typing import Tuple, Dict, Any
from flask import Flask
from auth import calendar_service
from calendar_service import list_changed_events, annotate_event, get_sync_token, save_sync_token
from cost_calculator import compute_meeting_cost
from user_service import list_active_users

app = Flask(__name__)


@app.get("/cron")
def cron() -> Tuple[Dict[str, Any], int]:
    """Main cron endpoint that processes all users' calendar events."""
    users = list_active_users()
    processed = 0
    skipped = 0

    for idx, email in enumerate(users):
        # Small yield to avoid hammering APIs
        if idx % 20 == 0:
            time.sleep(0.1)

        cal = calendar_service(email)
        sync_token = get_sync_token(email)

        # Fetch changes using sync tokens
        items, next_token = list_changed_events(cal, email, sync_token)
        # If token invalid, do a full resync
        if items is None and next_token is None:
            items, next_token = list_changed_events(cal, email, None)

        for event in items:
            cost_info = compute_meeting_cost(event)
            if cost_info['effective_cost'] < 0:
                skipped += 1
                continue
            
            try:
                annotate_event(cal, email, event, cost_info)
                processed += 1
            except Exception as e:
                # Log error but continue processing other events
                print(f"Failed to annotate event {email}:{event.get('id')}: {e}")

        # Save sync token for next run
        if next_token:
            save_sync_token(email, next_token)

    return {"processed": processed, "skipped": skipped}, 200
