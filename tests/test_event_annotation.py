#!/usr/bin/env python3
"""
Integration test for calendar event annotation.
Tests the full flow: authentication -> calendar access -> cost calculation -> event update.
"""
import sys
import os
import re
from datetime import datetime, timezone, timedelta

# Add src directory to path to import our modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Load .env file for configuration
from pathlib import Path
from dotenv import load_dotenv

project_root = Path(__file__).parent.parent
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

from auth import calendar_service
from calendar_service import list_changed_events, annotate_event
from cost_calculator import compute_meeting_cost
from config import config


def find_suitable_test_event(cal, calendar_id):
    """Find an internal-only meeting by searching through multiple time periods."""
    print("🔍 Searching for an internal-only meeting...")
    
    now = datetime.now(timezone.utc)
    days_back = 0
    total_checked = 0
    max_meetings = 200
    
    while total_checked < max_meetings:
        # Search in 30-day windows going backwards in time
        time_min = (now - timedelta(days=days_back + 30)).isoformat()
        time_max = (now - timedelta(days=days_back)).isoformat()
        
        print(f"  📅 Checking events from {(now - timedelta(days=days_back + 30)).strftime('%Y-%m-%d')} to {(now - timedelta(days=days_back)).strftime('%Y-%m-%d')}")
        
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
                if total_checked > max_meetings:
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
                
                # For this test, we want an internal-only meeting (no external attendees)
                if external_attendees:
                    print(f"    ⏭️  Skipping mixed meeting: '{event.get('summary', 'Untitled')}' ({len(internal_attendees)} internal, {len(external_attendees)} external)")
                    continue
                
                # Found an internal-only meeting!
                print(f"  ✅ Found internal-only meeting: '{event.get('summary', 'Untitled')}'")
                print(f"     Event ID: {event['id']}")
                print(f"     Start: {event['start']['dateTime']}")
                print(f"     Attendees: {len(attendees)} total (all internal)")
                print(f"     Checked {total_checked} meetings total")
                return event
                
        except Exception as e:
            print(f"  ❌ Error searching events in this period: {e}")
            break
        
        # Move to next 30-day window
        days_back += 30
        
        if not events:  # No events in this period, try going back further
            continue
    
    print(f"  ❌ No internal-only meetings found after checking {total_checked} meetings")
    return None


def test_event_annotation():
    """Test the complete event annotation flow."""
    print("🧪 Testing Calendar Event Annotation\n")
    
    # Check required environment variables
    test_user_email = os.environ.get('TEST_USER_EMAIL')
    if not test_user_email:
        print("❌ TEST_USER_EMAIL environment variable is required")
        print("   Set it to a user email in your domain, e.g.:")
        print("   export TEST_USER_EMAIL='test@yourdomain.com'")
        return False
    
    print(f"📋 Test Configuration:")
    print(f"   Domain: {config.domain}")
    print(f"   Default rate: ${config.default_rate}/hour")
    print(f"   Cost tag: {config.cost_tag}")
    print(f"   Internal only: {config.internal_only}")
    print(f"   Test user: {test_user_email}")
    print()
    
    try:
        # Step 1: Authenticate
        print("🔐 Step 1: Authenticating with Google Calendar API")
        cal = calendar_service(test_user_email)
        print(f"  ✅ Authenticated as: {test_user_email}")
        print()
        
        # Step 2: Find a test event
        print("📅 Step 2: Finding a suitable test event")
        test_event = find_suitable_test_event(cal, test_user_email)
        if not test_event:
            print("❌ Could not find a suitable test event")
            print("   Create a calendar event with:")
            print("   - Start and end times (not all-day)")
            print(f"   - At least one attendee from {config.domain}")
            print("   - Event in the past 7 days or next 7 days")
            return False
        print()
        
        # Step 3: Calculate cost
        print("💰 Step 3: Calculating meeting cost")
        cost_info = compute_meeting_cost(test_event)
        if cost_info['effective_cost'] < 0:
            print(f"  ❌ Event was skipped by cost calculation: {cost_info.get('skip_reason', 'unknown reason')}")
            return False
        
        print(f"  ✅ Effective cost: ${cost_info['effective_cost']}")
        if cost_info['invited_cost'] != cost_info['effective_cost']:
            print(f"  📊 Invited cost: ${cost_info['invited_cost']} ({cost_info['invited_count']} invited → {cost_info['effective_count']} attending)")
        print()
        
        # Step 4: Store original description for restoration
        original_description = test_event.get('description', '')
        print(f"📝 Step 4: Original event description:")
        if original_description:
            print(f"  {original_description[:100]}{'...' if len(original_description) > 100 else ''}")
        else:
            print("  (No original description)")
        print()
        
        # Step 5: Annotate the event
        print("✏️  Step 5: Annotating event with cost")
        annotate_event(cal, test_user_email, test_event, cost_info)
        print("  ✅ Event annotation completed")
        print()
        
        # Step 6: Verify the annotation
        print("✔️  Step 6: Verifying annotation was applied")
        
        # Re-fetch the event to see changes
        updated_event = cal.events().get(
            calendarId=test_user_email,
            eventId=test_event['id'],
            fields="description,extendedProperties"
        ).execute()
        
        updated_description = updated_event.get('description', '')
        extended_props = updated_event.get('extendedProperties', {}).get('private', {})
        
        # Check if cost tag is in description - now looks for the new format
        cost_tag_pattern = re.escape(config.cost_tag) + r":.*?\$\d+"
        cost_found_in_desc = re.search(cost_tag_pattern, updated_description, re.DOTALL)
        
        # Check if cost is in extended properties
        effective_cost_in_props = extended_props.get('effectiveCost')
        invited_cost_in_props = extended_props.get('invitedCost')
        
        if cost_found_in_desc and effective_cost_in_props:
            print("  ✅ Cost annotation found in event description")
            print("  ✅ Cost stored in extended properties")
            print(f"  💰 Cost in description: {cost_found_in_desc.group()}")
            print(f"  💰 Effective cost in properties: ${effective_cost_in_props}")
            if invited_cost_in_props and invited_cost_in_props != effective_cost_in_props:
                print(f"  💰 Invited cost in properties: ${invited_cost_in_props}")
            
            # Verify the costs match
            if effective_cost_in_props == str(cost_info['effective_cost']):
                print("  ✅ Cost values are consistent")
            else:
                print(f"  ⚠️  Cost mismatch: calculated {cost_info['effective_cost']}, stored {effective_cost_in_props}")
            
        else:
            print("  ❌ Cost annotation not found or incomplete")
            if not cost_found_in_desc:
                print("    - Missing cost in description")
            if not effective_cost_in_props:
                print("    - Missing effective cost in extended properties")
            return False
        
        print()
        print("🎉 Test completed successfully!")
        print()
        print("📋 Summary:")
        print(f"   Event: {test_event.get('summary', 'Untitled')}")
        print(f"   Effective cost calculated: ${cost_info['effective_cost']}")
        if cost_info['invited_cost'] != cost_info['effective_cost']:
            print(f"   Invited cost calculated: ${cost_info['invited_cost']}")
        print(f"   Annotation applied: ✅")
        print(f"   Verification passed: ✅")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_cost_calculation_only():
    """Test just the cost calculation without modifying events."""
    print("🧪 Testing Cost Calculation Only (No Event Modification)\n")
    
    test_user_email = os.environ.get('TEST_USER_EMAIL')
    if not test_user_email:
        print("❌ TEST_USER_EMAIL environment variable is required")
        return False
    
    try:
        # Authenticate and find event
        cal = calendar_service(test_user_email)
        test_event = find_suitable_test_event(cal, test_user_email)
        
        if not test_event:
            print("❌ Could not find suitable test event")
            return False
        
        # Calculate cost and display results
        cost = compute_meeting_cost(test_event)
        
        print(f"📊 Cost Calculation Results:")
        print(f"   Event: {test_event.get('summary', 'Untitled')}")
        print(f"   Attendees: {len(test_event.get('attendees', []))}")
        
        attendees = test_event.get('attendees', [])
        internal_count = len([a for a in attendees if a.get('email', '').endswith(f"@{config.domain}")])
        print(f"   Internal attendees: {internal_count}")
        
        # Calculate duration
        start_str = test_event['start']['dateTime']
        end_str = test_event['end']['dateTime']
        start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        duration = (end_dt - start_dt).total_seconds() / 3600
        print(f"   Duration: {duration} hours")
        
        if cost >= 0:
            print(f"   💰 Calculated cost: ${cost}")
            print(f"   📈 Rate breakdown: {internal_count} people × ${config.default_rate}/hr × {duration} hrs = ${cost}")
        else:
            print(f"   ⏭️  Event skipped (cost = {cost})")
        
        return True
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test meeting cost calculation and event annotation")
    parser.add_argument('--calc-only', action='store_true', 
                       help='Only test cost calculation, do not modify events')
    args = parser.parse_args()
    
    if args.calc_only:
        success = test_cost_calculation_only()
    else:
        print("⚠️  This test will modify a real calendar event!")
        print("   Make sure you're using a test calendar/account.")
        print("   Use --calc-only flag to test without modifications.")
        print()
        response = input("Continue with event modification test? (y/N): ")
        if response.lower() != 'y':
            print("Test cancelled.")
            sys.exit(0)
        
        success = test_event_annotation()
    
    sys.exit(0 if success else 1)