# Meeting Cost Calculator Tests

This directory contains tests for the Meeting Cost Calculator that validate the cost calculation and calendar event annotation functionality.

## Test Overview

The tests validate two core functions:
1. **Cost Calculation** - Tests the `compute_meeting_cost()` function with various scenarios
2. **Event Annotation** - Tests the full flow: authentication → calendar access → cost calculation → event update

## Quick Setup

### 1. Copy Configuration Files
```bash
# From the project root directory
cp .env_sample .env
cp credentials.json.sample credentials.json
```

### 2. Fill in Your Configuration

Edit `.env` with your actual values:
```bash
# Required
DOMAIN=your-domain.com
GOOGLE_CREDENTIALS_PATH=./credentials.json
TEST_USER_EMAIL=test@your-domain.com

# Optional (defaults shown)
DEFAULT_RATE=125
COST_TAG=[[MEETING_COST]]
INTERNAL_ONLY=true
```

Edit `credentials.json` with your Google Cloud service account JSON key.

### 3. Validate Setup
```bash
cd tests/
python3 setup_test_env.py
```

## Google Cloud Prerequisites

### Step 1: Create a Service Account in Google Cloud Console

1. **Navigate to Google Cloud Console**
   - Go to [console.cloud.google.com](https://console.cloud.google.com)
   - Select your project (or create a new one if needed)

2. **Enable Required APIs**
   - Go to "APIs & Services" → "Library"
   - Search for and enable these APIs:
     - **Google Calendar API**
     - **Admin SDK API** 
     - **Cloud Firestore API** (for storing sync tokens)

3. **Create the Service Account**
   - Go to "IAM & Admin" → "Service Accounts"
   - Click "**Create Service Account**"
   - **Service account name**: `meeting-cost-calculator`
   - **Service account ID**: Will auto-populate (e.g., `meeting-cost-calculator@your-project.iam.gserviceaccount.com`)
   - **Description**: `Service account for Meeting Cost Calculator with Domain-Wide Delegation`
   - Click "**Create and Continue**"

4. **Grant Service Account Roles** (Step 2 of 3)
   - **Important**: For this application, you don't need to grant any Google Cloud project roles
   - The service account will get permissions through Domain-Wide Delegation in Google Workspace
   - Click "**Continue**" (leave roles empty)

5. **Grant Users Access** (Step 3 of 3)
   - You can skip this step for now
   - Click "**Done**"

### Step 2: Enable Domain-Wide Delegation

1. **In the Service Accounts list**, click on your newly created service account
2. Go to the "**Details**" tab
3. Scroll down to "**Domain-wide delegation**" section
4. Check the box "**Enable Google Workspace Domain-wide Delegation**"
5. **Product name for consent screen**: `Meeting Cost Calculator`
6. Click "**Save**"
7. **Copy the Client ID** - you'll need this for Google Workspace Admin Console

### Step 3: Create and Download Service Account Key

1. **Still in the service account details**, go to the "**Keys**" tab
2. Click "**Add Key**" → "**Create new key**"
3. Select "**JSON**" format
4. Click "**Create**"
5. The JSON file will download automatically
6. **Copy the entire contents** of this downloaded file into your `credentials.json`

### Step 4: Configure Domain-Wide Delegation in Google Workspace Admin

⚠️ **Note**: You must be a Google Workspace Super Admin to complete this step.

1. **Go to Google Workspace Admin Console**
   - Navigate to [admin.google.com](https://admin.google.com)
   - Sign in with your Super Admin account

2. **Navigate to API Controls**
   - Click "**Security**" in the left sidebar
   - Click "**Access and data control**"
   - Click "**API controls**"

3. **Manage Domain-Wide Delegation**
   - Scroll down to "**Domain-wide delegation**" section
   - Click "**Manage Domain-Wide Delegation**"

4. **Add the Service Account**
   - Click "**Add new**"
   - **Client ID**: Paste the Client ID from Step 2 (looks like a long number)
   - **OAuth Scopes**: Enter these **exact** scopes (comma-separated):
     ```
     https://www.googleapis.com/auth/calendar,https://www.googleapis.com/auth/admin.directory.user.readonly
     ```
   - **Description**: `Meeting Cost Calculator - Calendar and Directory access`
   - Click "**Authorize**"

### Step 5: Verify Your Service Account JSON

Your `credentials.json` file should look like this structure:
```json
{
  "type": "service_account",
  "project_id": "your-project-id",
  "private_key_id": "key-id-here",
  "private_key": "-----BEGIN PRIVATE KEY-----\nYOUR-PRIVATE-KEY-HERE\n-----END PRIVATE KEY-----\n",
  "client_email": "meeting-cost-calculator@your-project.iam.gserviceaccount.com",
  "client_id": "123456789012345678901",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/...",
  "universe_domain": "googleapis.com"
}
```

**Key fields to verify:**
- ✅ `"type": "service_account"` (not "installed")
- ✅ `"client_email"` ends with your project ID
- ✅ `"private_key"` contains the full key with BEGIN/END markers

### Common Setup Issues

**"Domain-Wide Delegation not showing"**
- Make sure you enabled it in the service account Details tab first

**"OAuth scopes format error"**  
- Enter scopes exactly as shown above, comma-separated, no spaces
- Don't add quotes or brackets

**"Permission denied errors"**
- Wait 5-10 minutes for delegation changes to propagate
- Verify the Client ID matches exactly between Google Cloud and Workspace Admin

**"Service account has no private key"**
- You must create a JSON key in the "Keys" tab
- The downloaded file contains the private key needed for authentication

## Running Tests

### 1. Cost Calculation Test (Unit Test)
```bash
cd tests/
python3 test_cost_calculation.py
```

Tests cost calculation logic without requiring API access:
- Internal vs external attendee filtering
- Duration calculation from event timestamps
- Edge cases (all-day events, no attendees, declined attendees)

### 2. Live Event Annotation Test (Integration Test)

**Safe Mode** (no event modifications):
```bash
cd tests/
python3 test_event_annotation.py --calc-only
```

**Full Integration Test** (modifies events):
```bash
cd tests/
python3 test_event_annotation.py
```

⚠️ **Warning**: The full test will modify actual calendar events. Use a test calendar/user account.

## Expected Outputs

### Cost Calculation Test
```
✅ Testing: Internal-only meeting (2 attendees, 1 hour)
  ✅ Expected: 250, Got: 250

✅ Testing: Mixed internal/external (should be skipped if INTERNAL_ONLY=true)
  ✅ Expected: -1, Got: -1

✅ Testing: All-day event (should be skipped)
  ✅ All-day event correctly skipped
```

### Event Annotation Test (Safe Mode)
```
📁 Loaded environment from: /path/to/.env
✅ Authenticated as: test@your-domain.com
✅ Found suitable event: "Team Standup" 
💰 Calculated cost: $375
📈 Rate breakdown: 3 people × $125/hr × 1.0 hrs = $375
```

### Event Annotation Test (Full)
```
✅ Authenticated as: test@your-domain.com
✅ Found suitable event: "Team Standup"
✅ Calculated cost: $375
✅ Event annotation completed
✅ Cost annotation found in event description
✅ Cost stored in extended properties
💰 Cost in description: [[MEETING_COST]] $375
💰 Cost in properties: $375
```

## Test Requirements

For integration tests, ensure your test user has calendar events with:
- Start and end times (not all-day)
- At least one attendee from your domain
- Event is not declined by all attendees
- Event created within the past 7 days or next 7 days

## Troubleshooting

### Configuration Issues
```bash
# Run setup validation
python3 setup_test_env.py
```

### Common Problems

**"No .env file found"**
- Copy `.env_sample` to `.env` and fill in values

**"Credentials file not found"** 
- Copy `credentials.json.sample` to `credentials.json`
- Add your actual Google Cloud service account JSON

**"Authentication failed"**
- Verify Domain-Wide Delegation is enabled
- Check OAuth scopes are delegated in Admin Console
- Ensure service account has access to test user's calendar

**"No suitable events found"**
- Create a test calendar event with internal attendees
- Event must have specific start/end times (not all-day)
- Event should be within past/next 7 days

## File Structure
```
tests/
├── test.md                      # This documentation
├── setup_test_env.py           # Environment validation
├── test_cost_calculation.py    # Unit tests
├── test_event_annotation.py    # Integration tests
└── README.md                   # Quick reference
```