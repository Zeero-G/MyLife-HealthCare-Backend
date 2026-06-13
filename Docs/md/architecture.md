<br/><div align="center">

# 🏥 MYLIFE — Patient-Owned Healthcare Platform

**A privacy-first, interoperable health record system built for Sri Lanka**


<img src="logos/logo.png" alt="MYLIFE Logo" width="200" />

</div>

---

## 🏛 System Architecture Overview

MYLIFE uses a **Simplified Microservices Architecture**, trimmed down to 5 core microservices for buildability, maintainability, and ease of deployment. 

By relying on direct REST communication and Supabase (PostgreSQL + Auth + Storage), we abstracted away the need for message brokers (RabbitMQ) and separate caching layers (Redis) for the MVP.

### 💻 Technology Stack

*   **Frontend:** React.js + TypeScript, Tailwind CSS, Axios + React Query, deployed on Vercel.
*   **Backend:** FastAPI (Python), JWT Authentication, deployed on Railway/Render.
*   **Database & Storage:** Supabase PostgreSQL, Supabase Storage (for files), Supabase Auth SDK.
*   **AI Processing:** Claude API (Anthropic).

---

## 🧩 The 5 Microservices

### 1️⃣ Authentication Service (Port 8001)
Handles all user identity, authentication, roles, and permissions.
*   **Responsibilities:** Registration/Login, JWT token issue/refresh, Role management (Patient, Doctor, Admin), Password reset.
*   **DB Tables:** `users`, `roles`, `sessions`
*   **Endpoints:** `/auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/me`

### 2️⃣ Medical Records Service (Port 8002)
The core of the platform. Stores and manages all health records, QR sharing, and emergency profiles.
*   **Responsibilities:** Medical records & diagnoses, Medication & allergy history, QR code sharing, Emergency profile (offline-safe), SOS alerts.
*   **DB Tables:** `medical_records`, `diagnoses`, `medications`, `shared_records`, `emergency_profiles`
*   **Endpoints:** `/records` (GET/POST/PUT/DELETE), `/records/share-qr`, `/emergency/profile/{userId}`

### 3️⃣ Family & Profile Service (Port 8003)
Manages linked family accounts, caregivers, children, and women's health tracking.
*   **Responsibilities:** Link/unlink family accounts, Caregiver & child profiles, Menstrual & pregnancy tracking, Elderly parent management.
*   **DB Tables:** `linked_accounts`, `family_profiles`, `menstrual_cycles`, `pregnancy_records`, `caregiver_permissions`
*   **Endpoints:** `/family/link`, `/family/members`, `/family/unlink`, `/health/cycle`, `/health/pregnancy`

### 4️⃣ AI Processing Service (Port 8004)
Extracts structured data from uploaded medical documents using the Claude API.
*   **Responsibilities:** Accept uploaded PDF/images, Send to Claude API for extraction, Return structured medical data & confidence scoring.
*   **DB Tables:** `uploaded_documents`, `extracted_reports`
*   **Endpoints:** `/ai/process`, `/ai/results/{id}`, `/ai/summary`

### 5️⃣ Notification Service (Port 8005)
Sends emails and push notifications for key events. Called directly by other services.
*   **Responsibilities:** Email notifications, Push notifications (Firebase FCM), Appointment/Emergency/Verification alerts.
*   **DB Tables:** `notifications`, `notification_logs`
*   **Endpoints:** `/notify/email`, `/notify/push`, `/notify/reminder`

---

## 🗄 Database Architecture

All services use a shared **Supabase PostgreSQL** instance with **separate schemas** per service (`auth_schema`, `medical_schema`, `family_schema`, `ai_schema`, `notification_schema`). Each service reads and writes *only* its own schema.

File Storage utilizes **Supabase Storage Buckets** (e.g., `medical-docs`, `profile-pictures`).

---

## 🔄 Inter-Service Communication

All communication is synchronous **REST (HTTP)**.
*   **Medical → Auth:** Validate JWT token for protected routes.
*   **Medical → Notification:** Send email/push notification after record upload.
*   **Family → Auth:** Check user roles for family permissions.
*   **AI → Medical:** Return extracted data to store in `medical_schema`.
*   **AI → Notification:** Send email when extraction is complete.

---

## 🔒 Security Features (Simplified)

*   **Authentication:** JWT tokens (Access + Refresh).
*   **Authorization & Privacy:** Supabase Row Level Security (RLS), Role-based access control, Consent before record sharing.
*   **Validation & Logging:** Input validation via Pydantic, Audit log table per service.
*   **Transport:** HTTPS on all endpoints, CORS enforced at gateway (NGINX).

---

## ⚙️ Key Flow: Upload & Process Medical Record

1.  **Upload:** Patient uploads PDF via React frontend.
2.  **Route:** Request hits NGINX gateway → routed to Medical Records Service (8002).
3.  **Validate:** Medical Service validates JWT with Auth Service (8001).
4.  **Store:** File saved to Supabase Storage; metadata saved to `medical_schema`.
5.  **Process Call:** Medical Service calls AI Service (8004) with the file URL.
6.  **Extract Data:** AI Service sends file to Claude API → retrieves structured data.
7.  **Save Extraction:** Extracted data saved to `ai_schema.extracted_reports`.
8.  **Notify:** AI Service calls Notification Service (8005) → email sent to patient.
9.  **View:** Patient refreshes app → sees verified, extracted record.

---

## 📦 Project Setup

```yml
# Gateway Routing (NGINX)
/auth     → 8001
/records  → 8002
/family   → 8003
/ai       → 8004
/notify   → 8005
```

Deployment is handled via **Docker Compose**:
`docker-compose up --build -d` runs all 5 microservices along with the NGINX API gateway in a unified environment.