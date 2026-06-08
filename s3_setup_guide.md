# AWS S3 Setup Guide — MyLife Healthcare Document Upload

## Overview: How the Upload Flow Works

```
Frontend                    Backend                     AWS S3
   │                           │                           │
   │─ GET /records/presign ──▶ │                           │
   │                           │── boto3: generate ──────▶ │
   │◀─ { presigned_url,        │   presigned PUT URL       │
   │     public_url }          │                           │
   │                           │                           │
   │── PUT file directly ──────────────────────────────▶  │  (no backend proxy)
   │   (with progress bar)     │                          [S3]
   │                           │                           │
   │─ POST /records/confirm ─▶ │                           │
   │                           │── /ai/process ──▶ [AI Service]
   │◀─ { file_url, message }   │   (Gemini scans S3 URL)
```

---

## Step 1 — Create the S3 Bucket

1. Go to [AWS S3 Console](https://s3.console.aws.amazon.com/)
2. Click **Create bucket**
3. Fill in:
   - **Bucket name**: e.g. `mylife-medical-docs` (globally unique)
   - **AWS Region**: `ap-south-1` (Mumbai — closest to Sri Lanka)
4. Under **Object Ownership**: select `ACLs disabled` (recommended)
5. Under **Block Public Access**: 
   - **UNCHECK** `Block all public access`
   - Confirm the warning checkbox
6. Click **Create bucket**

---

## Step 2 — Set Bucket Policy (Public Read)

Go to **Permissions → Bucket Policy** and paste this:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::YOUR_BUCKET_NAME/*"
    }
  ]
}
```

Replace `YOUR_BUCKET_NAME` with your actual bucket name.

This lets the Gemini AI service download the file from S3 using the public URL.

---

## Step 3 — Configure CORS (Required for Browser Direct Upload)

Go to **Permissions → Cross-origin resource sharing (CORS)** and paste:

```json
[
  {
    "AllowedHeaders": ["*"],
    "AllowedMethods": ["PUT", "GET", "HEAD"],
    "AllowedOrigins": [
      "http://localhost:5173",
      "http://localhost:3000",
      "https://mylife.vercel.app"
    ],
    "ExposeHeaders": ["ETag"],
    "MaxAgeSeconds": 3000
  }
]
```

Without this CORS policy the browser will fail with a CORS error when trying to PUT the file directly to S3.

---

## Step 4 — Create an IAM User with S3 Permissions

1. Go to IAM Console → **Users → Create user**
2. Username: `mylife-backend`
3. Under **Permissions** → choose **Attach policies directly**
4. Create a custom inline policy:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "s3:PutObject",
        "s3:GetObject",
        "s3:DeleteObject",
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::YOUR_BUCKET_NAME",
        "arn:aws:s3:::YOUR_BUCKET_NAME/*"
      ]
    }
  ]
}
```

5. After creating the user go to **Security Credentials → Create access key**
6. Choose **Application running outside AWS**
7. **Save the Access Key ID and Secret Access Key** — you only see the secret once!

---

## Step 5 — Fill in the .env File

Open `services/medical-records-service/.env` and replace the placeholders:

```env
AWS_ACCESS_KEY_ID=AKIA...your_key_here...
AWS_SECRET_ACCESS_KEY=abc123...your_secret_here...
AWS_REGION=ap-south-1
S3_BUCKET=mylife-medical-docs
```

---

## Step 6 — Rebuild the Backend

```bash
# Local dev
docker-compose -f docker-compose.local.yml up --build -d medical-records-service

# EC2 production
docker-compose up --build -d medical-records-service
```

---

## Step 7 — Verify

Hit Swagger at http://localhost:8002/docs and test:

1. `GET /records/presign-upload?filename=test.pdf&content_type=application/pdf` → should return `presigned_url` and `public_url`
2. PUT the file bytes to `presigned_url` using curl or the frontend
3. Call `POST /records/confirm-upload` with the `public_url`
4. Check your S3 bucket — file should appear, Gemini scan should queue

---

## Summary of All Changed Files

| File | What Changed |
|---|---|
| `medical-records-service/requirements.txt` | Added `boto3==1.34.0` |
| `medical-records-service/app/core/config.py` | Added `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `S3_BUCKET`, `S3_PRESIGN_EXPIRY` |
| `medical-records-service/app/routers/records.py` | Added `GET /presign-upload`, `POST /confirm-upload`; replaced Supabase storage in `POST /upload` with S3 |
| `medical-records-service/.env` | Added S3 env var placeholders to fill in |
| `src/api.ts` | Added `recordsAPI.presignUpload()`, `recordsAPI.confirmUpload()`, `uploadToS3()` helper |
| `src/components/UploadView.tsx` | Upload now uses 3-step S3 presigned flow with real-time progress bar |

---

## FAQ

**Q: Does the AI service need S3 credentials?**  
No. Gemini downloads the file from the public S3 HTTPS URL. No boto3 needed in the AI service.

**Q: Why presigned URL instead of proxy?**  
Browser uploads straight to S3 — no memory pressure on your EC2, no Nginx body size limits, faster uploads.

**Q: What region?**  
`ap-south-1` (Mumbai) is closest to Sri Lanka. `ap-southeast-1` (Singapore) also works well.
