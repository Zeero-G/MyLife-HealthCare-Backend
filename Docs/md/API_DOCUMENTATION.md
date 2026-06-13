# MyLife HealthCare - API Documentation & Endpoints

This document outlines all the available API endpoints across the MyLife HealthCare microservices network and explains how to access the interactive FastAPI documentation.

---

## 1. Interactive API Docs (Swagger UI & ReDoc)

Because the backend is built using **FastAPI**, it automatically generates interactive documentation tests (OpenAPI/Swagger) for every single endpoint. You do not need Postman to test your APIs!

### How to Access the Docs Locally
Since the microservices run on specific ports via Docker Compose, you can access the interactive documentation by navigating to the `/docs` path of the respective service's port:

*   **Auth Service (Port 8001):**
    *   Swagger UI: [http://localhost:8001/docs](http://localhost:8001/docs)
    *   ReDoc: [http://localhost:8001/redoc](http://localhost:8001/redoc)
*   **Medical Records Service (Port 8002):**
    *   Swagger UI: [http://localhost:8002/docs](http://localhost:8002/docs)
*   **Family Profile Service (Port 8003):**
    *   Swagger UI: [http://localhost:8003/docs](http://localhost:8003/docs)
*   **AI Processing Service (Port 8004):**
    *   Swagger UI: [http://localhost:8004/docs](http://localhost:8004/docs)
*   **Notification Service (Port 8005):**
    *   Swagger UI: [http://localhost:8005/docs](http://localhost:8005/docs)

*Note: In production behind the Nginx Gateway, you may need to explicitly expose or route the `/docs` path if you want to access them publicly.*

### How to Authenticate in Swagger
1. Open any `/docs` URL (e.g., `http://localhost:8001/docs`).
2. Click the green **Authorize** button on the top right.
3. Paste the `access_token` you received from the `/auth/login` endpoint.
4. You can now execute protected endpoints directly from the browser!

---

## 2. API Endpoints Reference

Below is the complete list of backend paths explicitly defined in the codebase. When calling these through the frontend or gateway, use port `80` (e.g., `http://localhost/auth/login`).

### 🔑 Auth Service (Gateway Prefix: `/auth`)
*Handles user registration, login, and JWT token management.*
*   `POST   /auth/register` - Register a new user
*   `POST   /auth/login`    - Login and get JWT access/refresh tokens
*   `POST   /auth/refresh`  - Obtain a new access token using a valid refresh token
*   `POST   /auth/logout`   - Log the user out (Client discards the token)
*   `GET    /auth/me`       - Get details of the currently logged-in user

### 🏥 Medical Records Service (Gateway Prefixes: `/records`, `/emergency`)
*Handles the user's patient records and emergency profile.*
*   **Records:**
    *   `GET    /records/`            - Retrieve all medical records for the authenticated user
    *   `POST   /records/`            - Create a new medical record
    *   `GET    /records/{record_id}` - Retrieve a specific medical record
    *   `PUT    /records/{record_id}` - Update a specific medical record
    *   `DELETE /records/{record_id}` - Delete a specific medical record
    *   `POST   /records/share-qr`    - Generate a temporary QR code share link for a document
    *   `POST   /records/upload`      - Upload an external file/document attached to a record
*   **Emergency:**
    *   `GET    /emergency/profile/{user_id}` - Retrieve the user's emergency/SOS profile

### 👨‍👩‍👧‍👦 Family Profile Service (Gateway Prefixes: `/family`, `/health`)
*Handles family account linking and women’s health tracking.*
*   **Family:**
    *   `GET    /family/members`                  - Retrieve a list of linked family members
    *   `POST   /family/link`                     - Link a new family member account
    *   `DELETE /family/unlink/{linked_user_id}`  - Unlink/remove a family member
*   **Women's Health:**
    *   `POST   /health/cycle`      - Log a new menstrual cycle entry
    *   `GET    /health/cycle`      - Retrieve log history for menstrual cycles
    *   `POST   /health/pregnancy`  - Log pregnancy tracking data
    *   `GET    /health/pregnancy`  - Retrieve pregnancy tracking data

### 🧠 AI Processing Service (Gateway Prefix: `/ai`)
*Handles AI-driven extraction and analysis of medical records.*
*   `POST   /ai/process`          - Send data or files for AI extraction processing
*   `GET    /ai/results/{doc_id}` - Fetch extraction results for a specific processed document
*   `GET    /ai/summary`          - Generate an AI summary of the user's overall health

### 🔔 Notification Service (Gateway Prefix: `/notify`)
*Handles sending system alerts (Internal service).*
*   `POST   /notify/email`    - Trigger an email notification
*   `POST   /notify/push`     - Trigger a mobile push notification
*   `POST   /notify/reminder` - Schedule a health or pill reminder

---

## 3. Best Practices for Frontend Integration
- **Authorization Header:** For all endpoints (except `/auth/login` and `/auth/register`), the frontend must include the JWT token in the HTTP headers:
  ```http
  Authorization: Bearer <your_access_token>
  ```
- **Error Handling:** If an endpoint returns a `401 Unauthorized` status, the frontend should intercept the request, call `/auth/refresh` to get a new token, and automatically retry the original request.