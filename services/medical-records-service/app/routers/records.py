"""
Records Router – CRUD + QR sharing for medical records.
All routes are protected by JWT (get_current_user dependency).

IMPORTANT: Specific routes (/share-qr, /family/{id}, /upload, /presign-upload,
/confirm-upload) MUST come before the generic /{record_id} route to avoid
FastAPI matching them as record IDs.
"""

import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, status, Query
import httpx
import boto3
from botocore.exceptions import ClientError, NoCredentialsError

from app.core.config import settings
from app.core.security import get_current_user
from app.core.database import supabase
from app.schemas.records_schemas import (
    CreateRecordRequest, UpdateRecordRequest, ShareQRRequest,
    RecordResponse, ShareQRResponse,
)

router = APIRouter()


def _s3_client():
    """Create a boto3 S3 client using credentials from settings."""
    if not settings.AWS_ACCESS_KEY_ID or not settings.S3_BUCKET:
        raise HTTPException(
            status_code=503,
            detail="S3 is not configured on the server. Set AWS_ACCESS_KEY_ID and S3_BUCKET."
        )
    return boto3.client(
        "s3",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _s3_public_url(key: str) -> str:
    """Return the public HTTPS URL for an S3 object."""
    return f"https://{settings.S3_BUCKET}.s3.{settings.AWS_REGION}.amazonaws.com/{key}"



# ── GET /records/ ─────────────────────────────────────────────
@router.get("/", response_model=list[RecordResponse])
async def list_records(current_user: dict = Depends(get_current_user)):
    result = supabase.table("medical_records") \
        .select("*") \
        .eq("user_id", current_user["sub"]) \
        .order("created_at", desc=True) \
        .execute()
    return result.data


# ── POST /records/share-qr ─────────────────────────────────── (BEFORE /{record_id})
@router.post("/share-qr", response_model=ShareQRResponse)
async def share_qr(payload: ShareQRRequest, current_user: dict = Depends(get_current_user)):
    # Verify the record belongs to the current user
    record_check = supabase.table("medical_records") \
        .select("id") \
        .eq("id", payload.record_id) \
        .eq("user_id", current_user["sub"]) \
        .execute()
    if not record_check.data:
        raise HTTPException(status_code=404, detail="Record not found")

    token = str(uuid.uuid4())
    expires_at = datetime.utcnow() + timedelta(hours=payload.expires_hours)

    supabase.table("shared_records").insert({
        "record_id": payload.record_id,
        "token": token,
        "expires_at": expires_at.isoformat(),
        "created_by": current_user["sub"],
    }).execute()

    share_url = f"https://mylife.vercel.app/shared/{token}"
    return ShareQRResponse(qr_token=token, share_url=share_url, expires_at=expires_at.isoformat())


# ── GET /records/presign-upload ──────────────────────────── (BEFORE /{record_id})
@router.get("/presign-upload")
async def presign_upload(
    filename: str = Query(..., description="Original filename e.g. report.pdf"),
    content_type: str = Query("application/octet-stream", description="MIME type of the file"),
    current_user: dict = Depends(get_current_user),
):
    """
    Returns a presigned S3 PUT URL so the frontend can upload a file directly
    to S3 without going through the backend.  Also returns the final public URL
    that should be passed to /confirm-upload after the PUT succeeds.
    """
    s3 = _s3_client()
    key = f"{current_user['sub']}/{uuid.uuid4()}_{filename}"
    try:
        presigned_url = s3.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET,
                "Key": key,
                "ContentType": content_type,
            },
            ExpiresIn=settings.S3_PRESIGN_EXPIRY,
        )
    except (NoCredentialsError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"Could not generate presigned URL: {e}")

    return {
        "presigned_url": presigned_url,
        "public_url": _s3_public_url(key),
        "key": key,
        "expires_in": settings.S3_PRESIGN_EXPIRY,
    }


# ── POST /records/confirm-upload ─────────────────────────── (BEFORE /{record_id})
@router.post("/confirm-upload")
async def confirm_upload(
    payload: dict,
    current_user: dict = Depends(get_current_user),
):
    """
    Called after the frontend has successfully PUT the file to S3.
    Triggers asynchronous AI extraction and returns the public S3 URL.

    Body: { "file_url": "https://…", "filename": "report.pdf" }
    """
    file_url: str = payload.get("file_url", "")
    if not file_url:
        raise HTTPException(status_code=422, detail="file_url is required")

    # Trigger AI service asynchronously (non-blocking)
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.AI_SERVICE_URL}/ai/process",
                json={"user_id": current_user["sub"], "file_url": file_url},
                timeout=10,
            )
    except Exception:
        pass  # AI failure must not block the upload confirmation

    return {
        "file_url": file_url,
        "message": "Upload confirmed. AI extraction queued.",
    }


# ── POST /records/upload ──────────────────────────────────── (BEFORE /{record_id})
@router.post("/upload")
async def upload_document(file: UploadFile = File(...), current_user: dict = Depends(get_current_user)):
    """Legacy: stream file through backend → S3. Prefer presign-upload for large files."""
    s3 = _s3_client()
    file_bytes = await file.read()
    key = f"{current_user['sub']}/{uuid.uuid4()}_{file.filename}"

    try:
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=key,
            Body=file_bytes,
            ContentType=file.content_type or "application/octet-stream",
        )
    except (NoCredentialsError, ClientError) as e:
        raise HTTPException(status_code=500, detail=f"S3 upload failed: {e}")

    public_url = _s3_public_url(key)

    # Trigger AI extraction (non-blocking)
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.AI_SERVICE_URL}/ai/process",
                json={"user_id": current_user["sub"], "file_url": public_url},
                timeout=10,
            )
    except Exception:
        pass

    return {"file_url": public_url, "message": "File uploaded to S3. AI extraction queued."}


# ── GET /records/family/{patient_id} ─────────────────────── (BEFORE /{record_id})
@router.get("/family/{patient_id}", response_model=list[RecordResponse])
async def list_family_records(patient_id: str, current_user: dict = Depends(get_current_user)):
    # 1. Verify that current_user is linked as a family member to patient_id
    link_check = supabase.table("linked_accounts") \
        .select("*") \
        .eq("owner_id", current_user["sub"]) \
        .eq("linked_user_id", patient_id) \
        .execute()

    if not link_check.data:
        raise HTTPException(status_code=403, detail="Not authorized to view these records")

    # 2. Fetch records for the linked patient
    result = supabase.table("medical_records") \
        .select("*") \
        .eq("user_id", patient_id) \
        .order("created_at", desc=True) \
        .execute()
    return result.data


# ── POST /records/ ─────────────────────────────────────────────
@router.post("/", response_model=RecordResponse, status_code=201)
async def create_record(payload: CreateRecordRequest, current_user: dict = Depends(get_current_user)):
    new_record = {
        "user_id": current_user["sub"],
        "title": payload.title,
        "record_type": payload.record_type,
        "description": payload.description,
        "doctor_name": payload.doctor_name,
        "visit_date": str(payload.visit_date) if payload.visit_date else None,
        "diagnosis": payload.diagnosis,
        "file_url": payload.file_url,
    }
    result = supabase.table("medical_records").insert(new_record).execute()

    # Async: notify patient via Notification Service
    try:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{settings.NOTIFICATION_SERVICE_URL}/notify/email",
                json={"user_id": current_user["sub"], "event": "record_created", "record_title": payload.title},
                timeout=5,
            )
    except Exception:
        pass   # Notification failure must not block the main response

    return result.data[0]


# ── GET /records/{record_id} ────────────────────────────────── (AFTER specific routes)
@router.get("/{record_id}", response_model=RecordResponse)
async def get_record(record_id: str, current_user: dict = Depends(get_current_user)):
    result = supabase.table("medical_records") \
        .select("*") \
        .eq("id", record_id) \
        .eq("user_id", current_user["sub"]) \
        .execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Record not found")
    return result.data[0]


# ── PUT /records/{record_id} ───────────────────────────────────
@router.put("/{record_id}", response_model=RecordResponse)
async def update_record(record_id: str, payload: UpdateRecordRequest, current_user: dict = Depends(get_current_user)):
    update_data = {k: v for k, v in payload.model_dump().items() if v is not None}
    result = supabase.table("medical_records") \
        .update(update_data) \
        .eq("id", record_id) \
        .eq("user_id", current_user["sub"]) \
        .execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Record not found")
    return result.data[0]


# ── DELETE /records/{record_id} ───────────────────────────────
@router.delete("/{record_id}", status_code=204)
async def delete_record(record_id: str, current_user: dict = Depends(get_current_user)):
    # Verify ownership before delete
    check = supabase.table("medical_records") \
        .select("id") \
        .eq("id", record_id) \
        .eq("user_id", current_user["sub"]) \
        .execute()
    if not check.data:
        raise HTTPException(status_code=404, detail="Record not found or not owned by you")

    supabase.table("medical_records") \
        .delete() \
        .eq("id", record_id) \
        .eq("user_id", current_user["sub"]) \
        .execute()
