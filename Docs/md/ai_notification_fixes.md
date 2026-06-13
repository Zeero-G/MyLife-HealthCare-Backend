# AI Document Scan + Notification Service Fixes

## What Was Changed

### 1. AI Processing Service — Switched to Gemini Vision

| File | Change |
|---|---|
| `app/routers/ai_processing.py` | Replaced Claude/Anthropic with **Gemini 1.5 Flash**. Added `/ai/process-upload` endpoint for direct file uploads. Added robust JSON extraction from Gemini response. |
| `app/core/config.py` | Replaced `CLAUDE_API_KEY` → `GEMINI_API_KEY` |
| `.env` | Added `GEMINI_API_KEY=REDACTED_API_KEY` |
| `requirements.txt` | Replaced `anthropic==0.28.0` → `google-generativeai==0.7.2`, added `python-multipart==0.0.9` |

**How it works now:**
- `POST /ai/process` — takes a `file_url`, downloads it, sends to Gemini Vision as an image/PDF, returns structured JSON
- `POST /ai/process-upload` — takes a direct file upload (multipart), analyses it with Gemini Vision (great for camera scans!)
- Gemini returns structured medical data: patient name, diagnosis, medications, lab results, doctor, dates, allergies, follow-up

### 2. Notification Service — Fixed Startup Crash

| File | Change |
|---|---|
| `app/routers/notifications.py` | Firebase init is now **graceful** — if credentials are dummy/missing, service starts normally and push is a no-op. Email and reminder routes work regardless. All DB operations wrapped in try/except so one failing table doesn't crash the response. |

**Root cause:** The `firebase-credentials.json` had a fake/dummy private key. Firebase Admin SDK tried to parse it on startup and crashed, killing the entire service.

**Fix:** Firebase init is now tried inside a nested try/except. If it fails, `_firebase_enabled = False` and push calls are silently skipped with a log warning. The service stays up.

---

## What You Need To Do

### Step 1 — Deploy to EC2

SSH into your EC2 and run:

```bash
cd ~/MyLife-HealthCare-Backend

# Pull the latest changes
git pull

# Rebuild and restart all containers
docker-compose down
docker-compose up --build -d

# Watch logs to confirm all services started
docker-compose logs -f --tail=30
```

### Step 2 — Verify the AI Service

```bash
# Health check
curl https://myhealth.jo3.org/ai/health

# Quick test with a public medical document image URL
curl -X POST https://myhealth.jo3.org/ai/process \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "your-user-id-here",
    "file_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/47/PNG_transparency_demonstration_1.png/280px-PNG_transparency_demonstration_1.png"
  }'
```

### Step 3 — Verify the Notification Service

```bash
# Health check (should now return 200, not crash)
curl https://myhealth.jo3.org/notify/health
```

---

## Optional: Real Firebase Push Notifications

If you want real push notifications later:

1. Go to [Firebase Console](https://console.firebase.google.com) → Your Project → Settings → Service Accounts
2. Click **Generate New Private Key** → download the JSON
3. Replace `services/notification-service/firebase-credentials.json` with it
4. Redeploy: `docker-compose up --build -d notification-service`

> [!NOTE]
> Push notifications are **not required** for the platform to work. Email notifications via Supabase Edge Functions are the primary channel.

---

## Frontend Integration (Document Scan)

To use the new upload endpoint from the frontend:

```javascript
// Direct file upload (e.g., from camera scan or file picker)
const formData = new FormData();
formData.append('user_id', userId);
formData.append('file', file); // File object from input

const response = await fetch(`${API_BASE}/ai/process-upload`, {
  method: 'POST',
  headers: { 'Authorization': `Bearer ${token}` },
  body: formData,
});
const result = await response.json();
// result.extracted_data has all the medical fields
```

```javascript
// URL-based (if file is already in Supabase Storage)
const response = await fetch(`${API_BASE}/ai/process`, {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${token}`
  },
  body: JSON.stringify({
    user_id: userId,
    file_url: supabasePublicUrl
  })
});
```
