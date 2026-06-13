# MyLife HealthCare - System Architecture & Workflow

This document provides a comprehensive overview of how the **MyLife HealthCare** system operates, covering the frontend application, the FastAPI microservices backend, the API gateway, and the Supabase PostgreSQL database.

---

## 1. System Overview

The application is split into a **Frontend Client** and a **Microservices Backend**.
All communication from the frontend passes through a centralized **Nginx API Gateway** which routes requests to the appropriate internal backend microservice. The microservices then communicate with a cloud-hosted **Supabase PostgreSQL Database**.

---

## 2. Infrastructure Components

### A. Frontend (React + Vite)
- **Tech Stack:** React 19, TypeScript, Vite, Tailwind CSS v4.
- **Workflow:** 
  - All API calls are routed through `src/api.ts`.
  - In local development, `vite.config.ts` uses a proxy to forward requests targeting `/auth`, `/records`, etc., to `http://localhost:80` (the Nginx gateway). This bypasses CORS issues.
  - **Auth State:** Stored globally via `AuthContext.tsx`. The API client automatically intercepts `401 Unauthorized` responses and silently uses the `refresh_token` to fetch a new `access_token` and retry the request.

### B. API Gateway (Nginx)
- **Container:** `mylife-gateway` running on Port `80`.
- **Role:** Acts as the single entry point for the frontend.
- **Routing Rules:**
  - `/auth/*` ➔ `mylife-auth` (Port 8001)
  - `/records/*` & `/emergency/*` ➔ `mylife-medical` (Port 8002)
  - `/family/*` & `/health/*` ➔ `mylife-family` (Port 8003)
  - `/ai/*` ➔ `mylife-ai` (Port 8004)
  - `/notify/*` ➔ `mylife-notification` (Port 8005)
- **Features:** It handles CORS headers globally and applies API rate limiting to prevent spam.

### C. Backend Microservices (FastAPI)
The backend is split into 5 distinct Python FastAPI microservices running in Docker containers. They talk to each other via a shared internal Docker network (`mylife-network`).
1. **Auth Service (`auth-service`):** Handles JWT generation, registration, login, and secure password hashing using raw `bcrypt`.
2. **Medical Records Service (`medical-records-service`):** Manages user health records, file documents, and emergency SOS profiles.
3. **Family Profile Service (`family-profile-service`):** Manages family account linking, permissions, and women's health cycle tracking.
4. **AI Processing Service (`ai-processing-service`):** Handles AI extraction and summarization of medical records.
5. **Notification Service (`notification-service`):** Handles email/SMS/push notifications triggered by other services.

### D. Database (Supabase / PostgreSQL)
Instead of putting all tables in the default `public` schema, the database uses **Custom Schemas** to perfectly isolate microservice data:
- `auth_schema`, `medical_schema`, `family_schema`, `ai_schema`, `notification_schema`.

**Crucial Database Security Rules:**
1. **Schema Exposure:** Because Supabase hides custom schemas from its REST API by default, these schemas must be manually enabled in **Supabase Dashboard > Project Settings > API > Exposed schemas**.
2. **Permissions (Grants):** The API roles (`anon`, `authenticated`, `service_role`) must be explicitly granted `USAGE` and `ALL PRIVILEGES` via SQL so they can read/write to the custom schemas.
3. **Service Key:** The Python microservices use the `SUPABASE_SERVICE_KEY` in their `.env` files to bypass frontend Row Level Security (RLS) restrictions when doing backend-to-database communication.

---

## 3. End-to-End Request Flow Example (User Registration)

Here is a step-by-step breakdown of how data moves when a new user registers:

1. **User Clicks Submit:** The user fills the Signup form on the Frontend React App.
2. **API Client:** `src/api.ts` makes a `POST /auth/register` request.
3. **Gateway Interception:** The Nginx container on `localhost:80` catches the request. Seeing the `/auth` prefix, it forwards the traffic to the internal `auth-service` container on port 8001.
4. **FastAPI Processing:** 
   - The Python code validates the email format.
   - It hashes the password using `bcrypt`.
5. **Database Insert:** The auth service utilizes the Supabase client (configured specifically to target `schema="auth_schema"`) to insert the user into `auth_schema.users`.
6. **JWT Generation:** The auth service generates a signed `access_token` and `refresh_token`.
7. **Response:** The tokens travel back through Nginx to the Frontend, which saves them in `localStorage` and logs the user into the Dashboard.

---

## 4. Local Development & Deployment Workflow

### **To Run Locally:**
1. Open the backend folder: `cd /home/malan/Desktop/ZeeroG/MyLife-HealthCare`
2. Spin up containers: `sudo docker-compose up --build -d`
3. Open the frontend folder: `cd /home/malan/Desktop/ZeeroG/MyLife-Frontend`
4. Start the Vite dev server: `npm run dev`
5. Test at `http://localhost:3000`.

### **To Deploy to Production:**
1. **Database:** Keep using Supabase (Cloud).
2. **Backend:** Rent a VPS (Ubuntu server). SSH into it, clone the backend repository, populate `.env` files with production keys, and run `sudo docker-compose up --build -d`. Point a domain (e.g., `api.yourdomain.com`) to the VPS IP and set up SSL (HTTPS) via Certbot in Nginx.
3. **Frontend:** Push the frontend repository to GitHub, connect it to Vercel/Netlify, and expose an environment variable `VITE_API_BASE_URL=https://api.yourdomain.com`. Vercel will build and host the website globally.

---

## 5. Noteworthy Custom Fixes Applied
- **Bcrypt Fix:** The standard FastAPI `passlib` library has a bug in Python 3.11+ causing 500 errors on passwords. The auth service was rewritten to bypass `passlib` and use raw `bcrypt` directly.
- **Nginx Aggregation:** The health check endpoint in Nginx was updated from `location /health` to `location = /health` strictly to prevent routing conflicts with the family service trackings (`/health/cycle`).
- **Python Build Caching:** For changes in Python files to reflect, Docker Compose caching requires running `sudo docker-compose down && sudo docker-compose build && sudo docker-compose up -d`.