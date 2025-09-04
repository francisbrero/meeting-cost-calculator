import math
from datetime import datetime
from typing import Dict, Any, List
from config import config


def internal_email(email: str) -> bool:
    """Check if email belongs to internal domain."""
    return email.lower().endswith(f"@{config.domain}")


def event_duration_hours(event: Dict[str, Any]) -> float:
    """Calculate event duration in hours."""
    start = event.get("start", {})
    end = event.get("end", {})
    
    start_time = start.get("dateTime")
    end_time = end.get("dateTime")
    
    # Skip all-day events (date only)
    if not start_time or not end_time:
        return 0.0
    
    start_dt = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    end_dt = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
    
    duration_seconds = max(0.0, (end_dt - start_dt).total_seconds())
    return duration_seconds / 3600.0


def compute_meeting_cost(event: Dict[str, Any], hourly_rate: float = None) -> Dict[str, int]:
    """
    Calculate meeting cost with invited vs effective attendee counts.
    Returns dict with 'invited_cost', 'effective_cost', and status info.
    Returns {'invited_cost': -1, 'effective_cost': -1} if event should be skipped.
    """
    if hourly_rate is None:
        hourly_rate = config.default_rate
    
    attendees = [a for a in event.get("attendees", []) if a.get("email")]
    
    # Skip if no valid duration
    hours = event_duration_hours(event)
    if hours <= 0:
        return {'invited_cost': -1, 'effective_cost': -1, 'skip_reason': 'no_duration'}
    
    # Filter to internal attendees only
    internal_attendees = [a for a in attendees if internal_email(a["email"])]
    
    # Skip mixed internal/external meetings if configured
    if config.internal_only and len(internal_attendees) != len(attendees):
        return {'invited_cost': -1, 'effective_cost': -1, 'skip_reason': 'mixed_meeting'}
    
    # Skip if no internal attendees
    if len(internal_attendees) == 0:
        return {'invited_cost': -1, 'effective_cost': -1, 'skip_reason': 'no_internal_attendees'}
    
    # NEW: Skip meetings with only 1 attendee (solo meetings)
    if len(internal_attendees) == 1:
        return {'invited_cost': -1, 'effective_cost': -1, 'skip_reason': 'solo_meeting'}
    
    # Calculate invited cost (all internal attendees regardless of response)
    invited_cost = int(round(hours * len(internal_attendees) * hourly_rate, 0))
    
    # Calculate effective cost based on responses
    # Count attendees who responded "yes" or "maybe" (or haven't responded yet)
    effective_attendees = []
    for attendee in internal_attendees:
        response = attendee.get("responseStatus", "needsAction").lower()
        if response in ["accepted", "tentative", "needsaction"]:  # yes, maybe, or no response
            effective_attendees.append(attendee)
    
    # If everyone declined, skip the meeting
    if len(effective_attendees) == 0:
        return {'invited_cost': -1, 'effective_cost': -1, 'skip_reason': 'all_declined'}
    
    # NEW: Skip if effective attendees is only 1 person
    if len(effective_attendees) == 1:
        return {'invited_cost': -1, 'effective_cost': -1, 'skip_reason': 'effective_solo_meeting'}
    
    effective_cost = int(round(hours * len(effective_attendees) * hourly_rate, 0))
    
    return {
        'invited_cost': invited_cost,
        'effective_cost': effective_cost,
        'invited_count': len(internal_attendees),
        'effective_count': len(effective_attendees),
        'hours': hours,
        'skip_reason': None
    }


def compute_meeting_cost_legacy(event: Dict[str, Any], hourly_rate: float = None) -> int:
    """
    Legacy function for backward compatibility.
    Returns single cost value or -1 if skipped.
    """
    result = compute_meeting_cost(event, hourly_rate)
    
    if result['effective_cost'] == -1:
        return -1
    
    # Return effective cost as the primary cost
    return result['effective_cost']