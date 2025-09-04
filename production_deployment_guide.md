# Production Deployment Guide

This document describes how to deploy the **Meeting Cost Calculator** to production on **Google Cloud Run**, annotate Google Calendar events company-wide, and schedule it to run continuously.

> Assumes: You’re a Google Workspace + GCP shop. You have org/admin access or can work with IT to complete the Workspace steps.

---

## 0) Overview

**Components**

* **Cloud Run** service (Python/Flask) — computes costs & annotates events
* **Firestore** (Native mode) — stores per-user Calendar sync tokens
* **Secret Manager** — stores Service Account (SA) JSON
* **Cloud Scheduler** — invokes `/cron` every 5–10 minutes
* **Workspace Domain-Wide Delegation (DWD)** — lets the SA impersonate users to read/write their calendars

**Key Env Vars**

* `DOMAIN` (e.g., `hginsights.com`)
* `DEFAULT_RATE` (e.g., `125`)
* `COST_TAG` (e.g., `[[MEETING_COST]]`)
* `INTERNAL_ONLY` (`true|false`)
* `GOOGLE_CREDENTIALS_JSON` (contents of SA key)
* *(optional)* `ADMIN_SUBJECT` (an internal admin/bot email for Directory reads)

---

## 1) Workspace (Google Admin) Setup

1. **Create a Service Account OAuth Client**

   * In **Google Cloud Console** (same GCP project you’ll deploy to), create a **Service Account** (e.g., `meeting-cost-bot@PROJECT_ID.iam.gserviceaccount.com`).
   * Create a **key** (JSON). You’ll store it in Secret Manager later.

2. **Enable Domain-Wide Delegation (DWD)**

   * Google Admin Console → **Security → API Controls → Domain-wide delegation** → **Add new**.
   * **Client ID**: the OAuth 2.0 Client ID of your service account (found in IAM → your SA → *Unique ID / Client ID*).
   * **Scopes** (comma-separated):

     ```
     https://www.googleapis.com/auth/calendar,
     https://www.googleapis.com/auth/admin.directory.user.readonly
     ```
   * Save.

3. **(Optional) Choose an Admin Subject**

   * Pick a bot/admin user (e.g., `ops-bot@yourdomain.com`) that has Directory “Users: Read” privileges.
   * You’ll set `ADMIN_SUBJECT=ops-bot@yourdomain.com` if you want Directory reads to always use that identity.

> ✅ When DWD is set, the SA can impersonate any user in your domain for the authorized scopes.

---

## 2) GCP Project Setup

1. **Create/Select Project & Set Region**

   ```bash
   gcloud config set project YOUR_PROJECT_ID
   gcloud config set run/region us-central1        # or your region
   ```

2. **Enable Required APIs**

   ```bash
   gcloud services enable run.googleapis.com \
     secretmanager.googleapis.com \
     firestore.googleapis.com \
     cloudscheduler.googleapis.com \
     admin.googleapis.com \
     calendar-json.googleapis.com
   ```

3. **Create Firestore (Native mode)**

   * Console → Firestore → **Create database** → **Native mode**, choose region (keep close to Cloud Run region).
   * No rules changes needed (server-side SDK uses IAM).

4. **Create & Configure Service Account (for Cloud Run)**

   ```bash
   gcloud iam service-accounts create meeting-cost-bot \
     --display-name="Meeting Cost Calculator"

   # Grant minimum roles
   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:meeting-cost-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/run.invoker"

   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:meeting-cost-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/datastore.user"          # Firestore access

   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:meeting-cost-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/secretmanager.secretAccessor"

   gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
     --member="serviceAccount:meeting-cost-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com" \
     --role="roles/logging.logWriter"
   ```

5. **Store SA Key in Secret Manager**

   * If you haven’t already created a key for the SA used for DWD, create one, then:

   ```bash
   echo '<PASTE-SA-KEY-JSON-HERE>' | gcloud secrets create meeting-cost-sa-key \
     --replication-policy="automatic" --data-file=-
   ```

---

## 3) Build & Deploy Cloud Run

From the repo root (with `src/Dockerfile`, `src/main.py`, `src/requirements.txt`):

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/meeting-cost
```

Deploy with minimal autoscaling + secure invocation:

```bash
gcloud run deploy meeting-cost \
  --image gcr.io/YOUR_PROJECT_ID/meeting-cost \
  --service-account meeting-cost-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --max-instances 10 \
  --min-instances 0 \
  --cpu 1 --memory 512Mi \
  --concurrency 20 \
  --set-env-vars DOMAIN=hginsights.com \
  --set-env-vars DEFAULT_RATE=125 \
  --set-env-vars COST_TAG='[[MEETING_COST]]' \
  --set-env-vars INTERNAL_ONLY=true \
  --set-env-vars WINDOW_DAYS=35 \
  --set-env-vars MAX_USERS=10000 \
  --set-env-vars ADMIN_SUBJECT=ops-bot@hginsights.com
```

Now attach the Secret value as an env var:

```bash
# Fetch secret payload at runtime and inject into env GOOGLE_CREDENTIALS_JSON
gcloud run services update meeting-cost \
  --set-secrets GOOGLE_CREDENTIALS_JSON=meeting-cost-sa-key:latest
```

> **Note:** The app expects `GOOGLE_CREDENTIALS_JSON` to contain the **full JSON** of the DWD-enabled SA key.

---

## 4) Create the Scheduler Job

1. **Get the service URL**

   ```bash
   SERVICE_URL=$(gcloud run services describe meeting-cost --format='value(status.url)')
   echo $SERVICE_URL
   ```

2. **Grant the Scheduler’s SA permission to invoke Cloud Run**

   * Scheduler uses its own SA (by default: `[PROJECT_NUMBER]-compute@developer.gserviceaccount.com` or you can create one).
   * Add **Run Invoker**:

   ```bash
   SCHED_SA="meeting-cost-scheduler@YOUR_PROJECT_ID.iam.gserviceaccount.com"
   gcloud iam service-accounts create meeting-cost-scheduler \
     --display-name="Meeting Cost Scheduler"

   gcloud run services add-iam-policy-binding meeting-cost \
     --member="serviceAccount:${SCHED_SA}" \
     --role="roles/run.invoker"
   ```

3. **Create the job (every 5 min) with OIDC auth**

   ```bash
   gcloud scheduler jobs create http meeting-cost-cron \
     --schedule="*/5 * * * *" \
     --uri="${SERVICE_URL}/cron" \
     --http-method=GET \
     --oidc-service-account-email="${SCHED_SA}"
   ```

> Adjust cadence to 10–15 minutes if you have a large org to reduce API pressure.

---

## 5) Smoke Test

* Manually run once:

  ```bash
  gcloud scheduler jobs run meeting-cost-cron
  ```
* Check **Cloud Run Logs** → you should see a response like:

  ```json
  {"processed": 123, "skipped": 45}
  ```
* Inspect a few **internal** events on calendars:

  * First line of description includes your `COST_TAG` and a `$` amount
  * `extendedProperties.private.meetingCost` populated (verify via API if desired)

**Common validations**

* Change attendees (add/remove internal) → cost updates on next run
* Add external to internal-only event:

  * If `INTERNAL_ONLY=true`, the annotator **skips** mixed meetings (no updates)
  * If `INTERNAL_ONLY=false`, it still annotates but only counts internal attendees in the sum

---

## 6) Operational Settings

**Recommended**

* **Alerting:**

  * Create log-based metric for `processed` count; alert if drops to 0 for >60 minutes
* **Quotas & Backoff:**

  * Start with every 10–15 minutes; scale down to 5 if needed
* **Autoscaling:**

  * `--max-instances 10` and `--concurrency 20` are safe starters; tune based on load
* **Logs retention:**

  * Follow org policy (e.g., 30–90 days)
* **Region:**

  * Keep Cloud Run, Firestore, and users’ primary region reasonably close

---

## 7) Security & Privacy

* **DWD Scopes:** Only `calendar` and `directory.user.readonly` are required
* **No salaries:** Phase 1 uses a **standard hourly rate**; no personal comp data
* **No notifications:** All patches use `sendUpdates=none` to avoid invite spam
* **Idempotent writes:** Uses a unique `COST_TAG` to replace a single line in the description
* **Opt-out:** You can add a simple skip rule (optional) to ignore meetings with `[no-cost]` in the title

---

## 8) Configuration Changes

Update env vars safely:

```bash
gcloud run services update meeting-cost \
  --set-env-vars DEFAULT_RATE=140 \
  --set-env-vars INTERNAL_ONLY=false
```

Roll back to previous revision:

```bash
gcloud run revisions list --service=meeting-cost
gcloud run services update-traffic meeting-cost --to-revisions REVISION_NAME=100
```

---

## 9) Troubleshooting

* **403 / impersonation errors**

  * Confirm Domain-Wide Delegation is configured with the exact Client ID and scopes
  * Ensure your SA key in Secret Manager matches the DWD-enabled SA

* **No annotations appear**

  * Check logs for `processed/skipped` counts
  * Ensure meetings are **internal** per your `INTERNAL_ONLY` setting
  * Reduce `WINDOW_DAYS` temporarily and re-deploy; trigger manually

* **Update emails are sent**

  * Ensure `sendUpdates="none"` is in the events.patch request (it is in our code)

* **Quota errors**

  * Increase run interval to every 10–15 minutes
  * Consider user sharding or reducing `MAX_USERS`

---

## 10) Next Steps / Phase 2

* Rate providers (Directory/Groups/HRIS) to move beyond flat rate
* Slack digest (weekly top costs & trends)
* Remove cost line if a meeting becomes mixed (optional behavior)
* Add Calendar Add-on for sidebar breakdown

---

## Appendix: One-liner Re-Deploy

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT_ID/meeting-cost && \
gcloud run deploy meeting-cost \
  --image gcr.io/YOUR_PROJECT_ID/meeting-cost \
  --service-account meeting-cost-bot@YOUR_PROJECT_ID.iam.gserviceaccount.com \
  --no-allow-unauthenticated \
  --max-instances 10 --min-instances 0 --cpu 1 --memory 512Mi --concurrency 20 \
  --set-env-vars DOMAIN=hginsights.com,DEFAULT_RATE=125,COST_TAG='[[MEETING_COST]]',INTERNAL_ONLY=true,WINDOW_DAYS=35,MAX_USERS=10000,ADMIN_SUBJECT=ops-bot@hginsights.com && \
gcloud run services update meeting-cost \
  --set-secrets GOOGLE_CREDENTIALS_JSON=meeting-cost-sa-key:latest
```

---
