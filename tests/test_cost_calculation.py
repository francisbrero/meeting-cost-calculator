#!/usr/bin/env python3
"""
Unit tests for meeting cost calculation logic.
Tests the compute_meeting_cost function with various event scenarios.
"""
import sys
import os
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

from cost_calculator import compute_meeting_cost, internal_email, event_duration_hours


def create_test_event(attendees, start_time=None, end_time=None, title="Test Meeting"):
    """Create a test calendar event with specified attendees and times."""
    if start_time is None:
        start_time = datetime.now(timezone.utc)
    if end_time is None:
        end_time = start_time + timedelta(hours=1)
    
    return {
        "id": "test_event_123",
        "summary": title,
        "start": {"dateTime": start_time.isoformat()},
        "end": {"dateTime": end_time.isoformat()},
        "attendees": [{"email": email} for email in attendees],
        "organizer": {"email": attendees[0] if attendees else "organizer@example.com"}
    }


def create_allday_event(attendees):
    """Create an all-day event (should be skipped)."""
    return {
        "id": "allday_event_123", 
        "summary": "All Day Event",
        "start": {"date": "2023-12-01"},
        "end": {"date": "2023-12-02"},
        "attendees": [{"email": email} for email in attendees]
    }


def test_cost_calculation():
    """Run cost calculation unit tests."""
    print("🧪 Testing Meeting Cost Calculation Logic\n")
    
    # Test configuration
    domain = os.environ.get("DOMAIN", "example.com")
    default_rate = float(os.environ.get("DEFAULT_RATE", "125"))
    
    print(f"Domain: {domain}")
    print(f"Default rate: ${default_rate}/hour")
    print(f"Internal only mode: {os.environ.get('INTERNAL_ONLY', 'true')}")
    print()
    
    test_cases = [
        {
            "name": "Internal-only meeting (2 attendees, 1 hour)",
            "attendees": [f"alice@{domain}", f"bob@{domain}"],
            "duration_hours": 1,
            "expected": int(2 * default_rate * 1)  # 2 people * rate * 1 hour
        },
        {
            "name": "Single person meeting (should be skipped - solo meetings excluded)", 
            "attendees": [f"alice@{domain}"],
            "duration_hours": 1,
            "expected": -1  # Solo meetings are now skipped
        },
        {
            "name": "Long meeting (3 attendees, 2.5 hours)",
            "attendees": [f"alice@{domain}", f"bob@{domain}", f"charlie@{domain}"],
            "duration_hours": 2.5,
            "expected": int(3 * default_rate * 2.5)  # 3 people * rate * 2.5 hours
        },
        {
            "name": "Mixed internal/external (should be skipped if INTERNAL_ONLY=true)",
            "attendees": [f"alice@{domain}", "external@otherdomain.com"],
            "duration_hours": 1,
            "expected": -1  # Should be skipped when INTERNAL_ONLY=true
        },
        {
            "name": "External-only meeting (should be skipped)",
            "attendees": ["external1@otherdomain.com", "external2@otherdomain.com"],
            "duration_hours": 1,
            "expected": -1  # Should be skipped (no internal attendees)
        },
        {
            "name": "No attendees (should be skipped)",
            "attendees": [],
            "duration_hours": 1,
            "expected": -1  # Should be skipped (no attendees)
        }
    ]
    
    # Run test cases
    passed = 0
    failed = 0
    
    for test_case in test_cases:
        print(f"📋 Testing: {test_case['name']}")
        
        # Create event with specified duration
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(hours=test_case['duration_hours'])
        event = create_test_event(test_case['attendees'], start_time, end_time)
        
        # Calculate cost using new format
        cost_result = compute_meeting_cost(event)
        actual_cost = cost_result['effective_cost']
        expected_cost = test_case['expected']
        
        # Check result
        if actual_cost == expected_cost:
            print(f"  ✅ Expected: {expected_cost}, Got: {actual_cost}")
            if 'skip_reason' in cost_result and cost_result['skip_reason']:
                print(f"    (Skipped: {cost_result['skip_reason']})")
            passed += 1
        else:
            print(f"  ❌ Expected: {expected_cost}, Got: {actual_cost}")
            if 'skip_reason' in cost_result and cost_result['skip_reason']:
                print(f"    (Skipped: {cost_result['skip_reason']})")
            failed += 1
        
        print()
    
    # Test all-day event
    print("📋 Testing: All-day event (should be skipped)")
    allday_event = create_allday_event([f"alice@{domain}", f"bob@{domain}"])
    allday_result = compute_meeting_cost(allday_event)
    if allday_result['effective_cost'] == -1:
        print(f"  ✅ All-day event correctly skipped ({allday_result['skip_reason']})")
        passed += 1
    else:
        print(f"  ❌ All-day event should be skipped, got: {allday_result['effective_cost']}")
        failed += 1
    
    print()
    
    # Test helper functions
    print("🔧 Testing Helper Functions:")
    
    # Test internal_email function
    internal_test = internal_email(f"test@{domain}")
    external_test = internal_email("test@external.com")
    
    if internal_test and not external_test:
        print("  ✅ internal_email() function working correctly")
        passed += 1
    else:
        print(f"  ❌ internal_email() failed: internal={internal_test}, external={external_test}")
        failed += 1
    
    # Test duration calculation
    start = datetime(2023, 12, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2023, 12, 1, 11, 30, tzinfo=timezone.utc)
    test_event = create_test_event([f"test@{domain}"], start, end)
    duration = event_duration_hours(test_event)
    
    if duration == 1.5:
        print("  ✅ event_duration_hours() function working correctly")
        passed += 1
    else:
        print(f"  ❌ event_duration_hours() failed: expected 1.5, got {duration}")
        failed += 1
    
    print()
    
    # Summary
    total_tests = passed + failed
    print(f"📊 Test Results: {passed}/{total_tests} passed")
    
    if failed == 0:
        print("🎉 All tests passed!")
        return True
    else:
        print(f"💥 {failed} test(s) failed")
        return False


if __name__ == "__main__":
    # Set default domain if not provided
    if "DOMAIN" not in os.environ:
        print("⚠️  DOMAIN environment variable not set, using 'example.com'")
        os.environ["DOMAIN"] = "example.com"
    
    success = test_cost_calculation()
    sys.exit(0 if success else 1)