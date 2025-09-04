# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Meeting Cost Calculator that automatically annotates Google Calendar events with their estimated cost. The system calculates meeting costs using the formula: `duration_hours × internal_attendee_count × default_rate` and adds this information directly to calendar events.

## Architecture

The project consists of two implementations:

### Current Implementation (`src/`)
- **Language**: Python 3.11 with Flask
- **Deployment**: Cloud Run service triggered by Cloud Scheduler every 5-10 minutes
- **Architecture**: Modular structure with separate components for auth, configuration, cost calculation, and calendar services
- **Dependencies**: Flask, Google APIs (Calendar, Admin SDK), Firestore, python-dotenv

### Legacy Implementation (`legacy_app/`)
- **Language**: Google Apps Script (JavaScript)
- **File**: `legacy_app/meeting_cost_calculator.js`
- **Purpose**: Original implementation, kept for reference

## Key Components

### Core Components
- **src/main.py** - Flask application with cron endpoint
- **src/config.py** - Centralized configuration management with .env file support
- **src/auth.py** - Google API authentication and service creation
- **src/user_service.py** - Google Workspace user enumeration
- **src/calendar_service.py** - Calendar API operations and event annotation
- **src/cost_calculator.py** - Meeting cost calculation logic with dual cost system

### Google Workspace Integration
- Uses Domain-Wide Delegation with service account impersonation
- Required scopes: `calendar` and `admin.directory.user.readonly`
- Stores sync tokens per user in Firestore for efficient incremental updates

## Development Commands

### Local Development
```bash
cd src/
pip install -r requirements.txt
python main.py
```

### Testing
```bash
# Run unit tests
python tests/test_cost_calculation.py

# Run integration test with real calendar
python tests/test_event_annotation.py

# Test multiple meetings for QA
python tests/test_multiple_meetings.py
```

### Docker Build
```bash
cd src/
docker build -t meeting-cost-calculator .
```

### Dependencies
Dependencies are managed in `src/requirements.txt`:
- flask
- google-auth, google-auth-httplib2
- google-api-python-client  
- google-cloud-firestore
- python-dotenv

## Configuration

The application uses .env file for configuration (copy from `.env_sample`):

### Required
- `DOMAIN` - Google Workspace domain (e.g., "company.com")
- `GOOGLE_CREDENTIALS_PATH` - Path to service account credentials JSON file

### Optional  
- `DEFAULT_RATE` - Hourly rate for cost calculation (default: 125)
- `COST_TAG` - Tag format for cost annotation (default: "[[Estimated Meeting Cost]]")
- `INTERNAL_ONLY` - Skip mixed internal/external meetings (default: true)
- `MAX_USERS` - Safety limit for user enumeration (default: 10000)
- `WINDOW_DAYS` - Event window for full sync fallback (default: 35)
- `ADMIN_SUBJECT` - Email for Directory API impersonation (optional)
- `TEST_USER_EMAIL` - Email for testing (required for test scripts)

## Important Implementation Details

### Cost Calculation Logic
- **Dual Cost System**: Calculates both invited cost (all attendees) and effective cost (only accepted/tentative/no-response attendees)
- **Solo Meeting Exclusion**: Skips meetings with only 1 attendee (both invited and effective)
- **Internal Only**: Only counts internal attendees (domain match)
- **Response Status Filtering**: Excludes declined attendees from effective cost
- **Duration-based**: Uses duration in hours multiplied by attendee count and hourly rate
- **Storage**: Stores both costs in `extendedProperties.private` (meetingCost, invitedCost, effectiveCost)

### Event Annotation
- **Visual Display**: Uses color-coded emojis (🟢 ≤$500, 🟠 >$500, 🔴 >$1000)
- **Dual Cost Display**: Shows effective cost prominently, with invited cost details when different
- **Format**: `[[Estimated Meeting Cost]]: 🟢 $250` or with details `└─ Invited cost: 🟠 $400 (4 invited → 2 attending)`
- **Idempotent Updates**: Uses regex pattern matching to avoid duplicates
- **Skip Logic**: Excludes solo meetings, mixed meetings (when INTERNAL_ONLY=true), all-day events, and meetings with no duration

### Sync Token Management
- Maintains per-user sync tokens in Firestore collection "meetingcost"
- Falls back to windowed sync if tokens become stale
- Handles pagination for large result sets

### Error Handling
- Graceful fallback when sync tokens expire
- Skips individual users/events on API errors without stopping the entire process
- Implements rate limiting and batch processing for large domains