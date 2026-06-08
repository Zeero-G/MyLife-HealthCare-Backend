"""
AI Processing Router – accepts document URLs/uploads, calls Gemini Vision API,
stores structured results, and notifies the patient.
"""

import uuid
import json
import base64
import re
import httpx
import asyncio
import random
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted, GoogleAPICallError
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from app.core.config import settings
from app.core.database import supabase

router = APIRouter()

# Configure Gemini
genai.configure(api_key=settings.GEMINI_API_KEY)


# ── Schemas ──────────────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    user_id: str
    file_url: str


class AIResultResponse(BaseModel):
    id: str
    user_id: str
    file_url: str
    extracted_data: dict
    confidence_score: Optional[float]
    status: str


# ── Prompt ───────────────────────────────────────────────────────────────────

EXTRACTION_PROMPT = """
You are an expert medical document analysis AI.
Carefully analyse the provided medical document and extract the following structured information.

Return ONLY a valid JSON object (no markdown, no commentary) with these exact keys:
{
  "patient_name": null,
  "patient_dob": null,
  "patient_gender": null,
  "diagnosis": [],
  "medications": [{"name": null, "dosage": null, "frequency": null}],
  "lab_results": [{"test_name": null, "value": null, "unit": null, "reference_range": null, "status": null}],
  "doctor_name": null,
  "hospital_clinic": null,
  "visit_date": null,
  "allergies": [],
  "follow_up_instructions": null,
  "document_type": null,
  "confidence_score": 0.85
}

Use null for any missing fields. Set confidence_score between 0.0 and 1.0 based on document clarity.
"""


# ── Helpers ───────────────────────────────────────────────────────────────────

def _extract_json_from_text(raw_text: str) -> dict:
    """Robustly extract a JSON object from Gemini's response text."""
    # Try direct parse first
    try:
        return json.loads(raw_text.strip())
    except json.JSONDecodeError:
        pass
    # Strip markdown code fences
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
    if match:
        try:
            return json.loads(match.group(1).strip())
        except json.JSONDecodeError:
            pass
    # Find first { ... } block
    match = re.search(r"(\{[\s\S]*\})", raw_text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    # Fallback – return raw text wrapped
    return {"raw_response": raw_text, "parse_error": "Could not parse JSON from Gemini response"}


async def _generate_content_with_retry(model, contents, max_retries=5, initial_delay=2.0):
    """Call Gemini's generate_content in a thread pool with exponential backoff on 429 errors."""
    delay = initial_delay
    loop = asyncio.get_running_loop()
    for attempt in range(max_retries):
        try:
            # run_in_executor runs blocking code in a thread pool to avoid blocking the event loop
            response = await loop.run_in_executor(None, lambda: model.generate_content(contents))
            return response
        except (ResourceExhausted, Exception) as e:
            err_msg = str(e).lower()
            is_rate_limit = (
                isinstance(e, ResourceExhausted)
                or "429" in err_msg
                or "quota exceeded" in err_msg
                or "resourceexhausted" in err_msg
            )
            if is_rate_limit and attempt < max_retries - 1:
                # Add jitter between 0 and 1.5 seconds
                sleep_time = delay + random.uniform(0, 1.5)
                await asyncio.sleep(sleep_time)
                delay *= 2.0  # exponential backoff
                continue
            raise e


async def _call_gemini_with_url(file_url: str) -> tuple[dict, float]:
    """Download file and send it to Gemini as inline data for vision analysis."""
    model = genai.GenerativeModel("gemini-2.5-flash")

    # Determine mime type from URL extension
    url_lower = file_url.lower()
    if url_lower.endswith(".pdf"):
        mime_type = "application/pdf"
    elif url_lower.endswith(".png"):
        mime_type = "image/png"
    elif url_lower.endswith(".jpg") or url_lower.endswith(".jpeg"):
        mime_type = "image/jpeg"
    elif url_lower.endswith(".webp"):
        mime_type = "image/webp"
    else:
        mime_type = "image/jpeg"  # default assumption

    try:
        # Download the file content
        async with httpx.AsyncClient(timeout=30) as http:
            response = await http.get(file_url)
            response.raise_for_status()
            file_bytes = response.content

        # Send to Gemini as inline data
        gemini_response = await _generate_content_with_retry(model, [
            EXTRACTION_PROMPT,
            {
                "mime_type": mime_type,
                "data": base64.b64encode(file_bytes).decode("utf-8"),
            },
        ])
    except Exception:
        # Fallback: send just the URL as text context (no vision)
        gemini_response = await _generate_content_with_retry(model, [
            f"{EXTRACTION_PROMPT}\n\nDocument URL: {file_url}\n"
            "Note: Analyse the document at this URL and extract all visible medical data."
        ])

    extracted = _extract_json_from_text(gemini_response.text)
    confidence = float(extracted.pop("confidence_score", 0.85))
    return extracted, confidence


async def _store_and_notify(doc_id: str, user_id: str, file_url: str,
                             extracted: dict, confidence: float) -> None:
    """Persist results and fire notification (best-effort)."""
    supabase.table("extracted_reports").insert({
        "document_id": doc_id,
        "user_id": user_id,
        "extracted_data": extracted,
        "confidence_score": confidence,
    }).execute()

    supabase.table("uploaded_documents") \
        .update({"status": "completed"}) \
        .eq("id", doc_id) \
        .execute()

    try:
        async with httpx.AsyncClient() as http:
            await http.post(
                f"{settings.NOTIFICATION_SERVICE_URL}/notify/email",
                json={"user_id": user_id, "event": "ai_extraction_complete"},
                timeout=5,
            )
    except Exception:
        pass  # Notification failure must not block the response


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/process", response_model=AIResultResponse, status_code=202)
async def process_document(payload: ProcessRequest):
    """
    Accepts a medical document URL, analyses it with Gemini Vision,
    stores structured results, and notifies the patient.
    """
    doc_id = str(uuid.uuid4())
    supabase.table("uploaded_documents").insert({
        "id": doc_id,
        "user_id": payload.user_id,
        "file_url": payload.file_url,
        "status": "processing",
    }).execute()

    try:
        extracted, confidence = await _call_gemini_with_url(payload.file_url)
        await _store_and_notify(doc_id, payload.user_id, payload.file_url, extracted, confidence)

        return AIResultResponse(
            id=doc_id,
            user_id=payload.user_id,
            file_url=payload.file_url,
            extracted_data=extracted,
            confidence_score=confidence,
            status="completed",
        )

    except Exception as e:
        supabase.table("uploaded_documents") \
            .update({"status": "failed"}) \
            .eq("id", doc_id) \
            .execute()
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {str(e)}")


@router.post("/process-upload", response_model=AIResultResponse, status_code=202)
async def process_uploaded_file(
    user_id: str = Form(...),
    file: UploadFile = File(...),
):
    """
    Accepts a direct file upload (image/PDF), analyses it with Gemini Vision,
    and returns structured medical data. Useful for on-device document scans.
    """
    doc_id = str(uuid.uuid4())
    file_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"

    supabase.table("uploaded_documents").insert({
        "id": doc_id,
        "user_id": user_id,
        "file_url": f"upload://{file.filename}",
        "status": "processing",
    }).execute()

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        gemini_response = await _generate_content_with_retry(model, [
            EXTRACTION_PROMPT,
            {
                "mime_type": mime_type,
                "data": base64.b64encode(file_bytes).decode("utf-8"),
            },
        ])
        extracted = _extract_json_from_text(gemini_response.text)
        confidence = float(extracted.pop("confidence_score", 0.85))

        await _store_and_notify(doc_id, user_id, f"upload://{file.filename}", extracted, confidence)

        return AIResultResponse(
            id=doc_id,
            user_id=user_id,
            file_url=f"upload://{file.filename}",
            extracted_data=extracted,
            confidence_score=confidence,
            status="completed",
        )

    except Exception as e:
        supabase.table("uploaded_documents") \
            .update({"status": "failed"}) \
            .eq("id", doc_id) \
            .execute()
        raise HTTPException(status_code=500, detail=f"AI extraction failed: {str(e)}")


@router.get("/results/{doc_id}", response_model=AIResultResponse)
async def get_result(doc_id: str):
    """Retrieve extraction results for a specific document."""
    result = supabase.table("extracted_reports") \
        .select("*") \
        .eq("document_id", doc_id) \
        .execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="Extraction result not found")
    r = result.data[0]
    return AIResultResponse(
        id=doc_id,
        user_id=r["user_id"],
        file_url="",
        extracted_data=r["extracted_data"],
        confidence_score=r["confidence_score"],
        status="completed",
    )


@router.get("/summary")
async def get_summary(user_id: str):
    """Returns all extraction results for a given user."""
    result = supabase.table("extracted_reports") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()
    return result.data
