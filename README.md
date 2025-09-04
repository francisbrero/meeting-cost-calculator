# Meeting Cost Calculator

This project automatically calculates the cost of internal meetings in Google Calendar and **annotates each event with its estimated cost**.

Inspired by Shopify’s meeting cost initiative, this tool helps teams become more intentional about meetings by showing the $$ impact directly in the invite.
[inspiration](https://finance.yahoo.com/news/shopify-cfo-explains-meeting-cost-105829140.html)

---

## Features

- Calculates cost = `duration_hours × internal_attendee_count × default_rate`
- Adds a cost line to the event description (idempotent, no duplicates)
- Stores numeric cost in `extendedProperties.private.meetingCost`
- Skips external meetings if `INTERNAL_ONLY=true`
- Runs as a Cloud Run service, triggered every 5–10 minutes by Cloud Scheduler

---

## Quick Start

1. **Workspace Setup**
   - Create a service account with **Domain-Wide Delegation** enabled
   - Grant scopes:
     - `https://www.googleapis.com/auth/calendar`
     - `https://www.googleapis.com/auth/admin.directory.user.readonly`

2. **GCP Setup**
   - Enable APIs: Calendar, Admin SDK, Firestore, Secret Manager, Cloud Run, Cloud Scheduler
   - Deploy the Docker container to Cloud Run
   - Store SA key JSON in Secret Manager

3. **Config**
   - Environment variables:
     - `DOMAIN=hginsights.com`
     - `DEFAULT_RATE=125`
     - `COST_TAG=[[MEETING_COST]]`
     - `INTERNAL_ONLY=true`
     - `GOOGLE_CREDENTIALS_JSON` = SA key JSON

4. **Schedule**
   - Create a Cloud Scheduler job to hit `/cron` every 5–10 min

---

## Roadmap

[] Add role/level-based rates (Directory, Groups, or HRIS integration)
[] Add Slack weekly digest (“Total meeting cost last week: $X”)
[] Add reporting pipeline into BigQuery / Databricks
[] Add a Google Calendar sidebar add-on for live per-meeting breakdown
