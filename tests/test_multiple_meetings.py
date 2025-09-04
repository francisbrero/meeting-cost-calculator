#!/usr/bin/env python3
"""
Test script to annotate multiple meetings for QA purposes.
Shows which meetings were processed and their costs.
"""
import sys
import os
import re
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Add src directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Load .env file for configuration
project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

from auth import calendar_service
from calendar_service import annotate_event
from cost_calculator import compute_meeting_cost
from config import config


def find_and_process_meetings(cal, calendar_id, max_meetings=3):
    """Find and process multiple internal meetings for testing."""
    print("🔍 Searching for internal meetings to process...")
    
    now = datetime.now(timezone.utc)
    days_back = 0
    total_checked = 0
    processed = []
    max_search = 100
    
    while len(processed) < max_meetings and total_checked < max_search:
        # Search in 30-day windows going backwards
        time_min = (now - timedelta(days=days_back + 30)).isoformat()
        time_max = (now - timedelta(days=days_back)).isoformat()
        
        print(f"  📅 Searching {(now - timedelta(days=days_back + 30)).strftime('%Y-%m-%d')} to {(now - timedelta(days=days_back)).strftime('%Y-%m-%d')}")
        
        try:
            events_result = cal.events().list(
                calendarId=calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                maxResults=50,
                singleEvents=True,
                orderBy='startTime',
                fields="items(id,summary,start,end,attendees,organizer,description,extendedProperties)"
            ).execute()
            
            events = events_result.get('items', [])
            print(f"  📊 Found {len(events)} events in this period")
            
            for event in events:
                total_checked += 1
                if len(processed) >= max_meetings:
                    break
                    
                # Check if event has start/end times (not all-day)
                if 'dateTime' not in event.get('start', {}):
                    continue
                    
                # Check if event has attendees
                attendees = event.get('attendees', [])
                if not attendees:
                    continue
                
                # Filter to only internal attendees
                internal_attendees = [a for a in attendees if a.get('email', '').endswith(f"@{config.domain}")]
                external_attendees = [a for a in attendees if not a.get('email', '').endswith(f"@{config.domain}")]
                
                # Skip if no internal attendees
                if not internal_attendees:
                    continue
                
                # For this test, we want internal-only meetings
                if external_attendees:
                    continue
                
                # Calculate cost using new format
                cost_info = compute_meeting_cost(event)
                if cost_info['effective_cost'] < 0:
                    if cost_info.get('skip_reason') == 'solo_meeting':
                        print(f"    ⏭️  Skipping solo meeting: '{event.get('summary', 'Untitled')}'")
                    continue
                
                # Process this meeting
                try:
                    print(f"  🎯 Processing: '{event.get('summary', 'Untitled')}'")
                    annotate_event(cal, calendar_id, event, cost_info)
                    
                    processed.append({
                        'title': event.get('summary', 'Untitled'),
                        'event_id': event['id'],
                        'start': event['start']['dateTime'],
                        'effective_cost': cost_info['effective_cost'],
                        'invited_cost': cost_info['invited_cost'],
                        'effective_count': cost_info['effective_count'],
                        'invited_count': cost_info['invited_count'],
                        'duration': cost_info['hours'],
                        'has_dual_cost': cost_info['invited_cost'] != cost_info['effective_cost']
                    })
                    
                    if cost_info['invited_cost'] != cost_info['effective_cost']:
                        print(f"      ✅ Annotated with dual costs: ${cost_info['effective_cost']} effective, ${cost_info['invited_cost']} invited")
                    else:
                        print(f"      ✅ Annotated with cost: ${cost_info['effective_cost']}")
                    
                except Exception as e:
                    print(f"      ❌ Failed to annotate: {e}")
                    
        except Exception as e:
            print(f"  ❌ Error searching events: {e}")
            break
        
        # Move to next time window
        days_back += 30
        
        if not events:
            continue
    
    return processed


def test_multiple_meetings():
    """Test multiple meeting annotations for QA."""
    print("🧪 Testing Multiple Meeting Annotations for QA")
    print("=" * 60)
    
    test_user_email = os.environ.get('TEST_USER_EMAIL')
    if not test_user_email:
        print("❌ TEST_USER_EMAIL environment variable is required")
        return False
    
    print(f"📋 Configuration:")
    print(f"   Domain: {config.domain}")
    print(f"   Test user: {test_user_email}")
    print(f"   Default rate: ${config.default_rate}/hour")
    print(f"   Cost tag: {config.cost_tag}")
    print()
    
    try:
        # Authenticate
        print("🔐 Authenticating with Google Calendar API...")
        cal = calendar_service(test_user_email)
        print(f"  ✅ Authenticated as: {test_user_email}")
        print()
        
        # Find and process meetings
        processed = find_and_process_meetings(cal, test_user_email, max_meetings=3)
        
        print("\n" + "=" * 60)
        print("📋 QA SUMMARY - Please check these meetings in your calendar:")
        print("=" * 60)
        
        if not processed:
            print("❌ No internal meetings found to process")
            return False
        
        for i, meeting in enumerate(processed, 1):
            # Determine cost category for effective cost
            effective_cost = meeting['effective_cost']
            if effective_cost > 1000:
                cost_category = "🔴 HIGH COST"
            elif effective_cost > 500:
                cost_category = "🟠 MEDIUM COST"
            else:
                cost_category = "🟢 LOW COST"
            
            print(f"\n{i}. 📅 {meeting['title']}")
            print(f"   💰 Effective Cost: ${effective_cost} ({cost_category})")
            
            if meeting['has_dual_cost']:
                invited_cost = meeting['invited_cost']
                if invited_cost > 1000:
                    invited_category = "🔴 HIGH"
                elif invited_cost > 500:
                    invited_category = "🟠 MEDIUM"
                else:
                    invited_category = "🟢 LOW"
                print(f"   💸 Invited Cost: ${invited_cost} ({invited_category})")
                print(f"   👥 Attendance: {meeting['invited_count']} invited → {meeting['effective_count']} attending")
            
            print(f"   📊 Details: {meeting['effective_count']} attendees × {meeting['duration']}h × ${config.default_rate}/h")
            print(f"   📅 When: {meeting['start']}")
            print(f"   🔗 Event ID: {meeting['event_id']}")
            
        print(f"\n✅ Successfully processed {len(processed)} meetings")
        print("👀 Please check your Google Calendar to verify the cost annotations appear correctly")
        print("   - Costs should appear at the top of event descriptions")
        print("   - Colors/emojis should match the cost levels shown above")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        return False


if __name__ == "__main__":
    success = test_multiple_meetings()
    sys.exit(0 if success else 1)