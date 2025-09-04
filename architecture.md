# Architecture Overview

## High-Level Design

The system is a Cloud Run service that:

1. Enumerates active Workspace users (Directory API)
2. Uses Calendar API sync tokens to fetch changed events
3. Filters to internal meetings
4. Computes meeting cost (attendees × duration × default_rate)
5. Updates the event description and extendedProperties
6. Persists sync tokens per-user in Firestore

A Cloud Scheduler job triggers the service every 5–10 minutes.

---

## Components

### Cloud Run Service

- Language: Python 3.11, Flask
- Responsibilities:
  - Handle `/cron` requests
  - Fetch & annotate meetings
  - Persist sync tokens

### Google Workspace

- APIs:
  - **Calendar API** — read/write events
  - **Admin SDK Directory API** — list active users
- Domain-Wide Delegation scopes:
  - `calendar`
  - `admin.directory.user.readonly`

### Firestore

- Stores sync tokens per user:
  ```json
  {
    "syncToken": "<token>"
  }
  ```

### Secret Manager

Stores service account JSON credentials

### Cloud Scheduler

Triggers Cloud Run /cron endpoint every 5–10 min

### Data Flow

1. Scheduler triggers service

2. Service loads SA creds + sync tokens

3. For each user:
    - Fetch changed events
    - Compute cost
    - Patch event with cost annotation
    - Save new sync token
4. Log metrics (processed, skipped) to Cloud Logging

### Future Extensions

- Rate provider layer (per role/level, group-based, or HRIS integration)
- Slack notifier (weekly digest)
- Reporting pipeline to BigQuery/Databricks
- Google Calendar Add-on (real-time sidebar)
