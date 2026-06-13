# MyLife Healthcare – Development & Deployment Guide

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        PRODUCTION                               │
│                                                                 │
│  Vercel (Frontend)          EC2 (Backend)                       │
│  ─────────────────          ──────────────────────────────────  │
│  https://my-life-health  →  https://myhealth.jo3.org (:443)    │
│  care-frontend.vercel.app   NGINX Gateway (SSL)                 │
│                               ├── /auth       → :8001          │
│                               ├── /records    → :8002          │
│                               ├── /emergency  → :8002          │
│                               ├── /appointments→ :8002         │
│                               ├── /family     → :8003          │
│                               ├── /health     → :8003          │
│                               ├── /ai         → :8004          │
│                               └── /notify     → :8005          │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     LOCAL DEVELOPMENT                           │
│                                                                 │
│  Browser                                                        │
│    → http://localhost:3000 (Vite Dev Server)                    │
│        → Vite Proxy → http://localhost:80 (NGINX, no SSL)       │
│                          ├── /auth       → :8001               │
│                          └── ... (same as above)               │
└─────────────────────────────────────────────────────────────────┘
```

---

## Files Reference

| File | Purpose |
|---|---|
| `docker-compose.yml` | **Production only** — EC2, uses SSL nginx.conf |
| `docker-compose.local.yml` | **Local dev only** — No SSL, uses nginx.local.conf |
| `gateway/nginx.conf` | Production NGINX config (HTTPS + SSL certs) |
| `gateway/nginx.local.conf` | Local NGINX config (HTTP only, no certs needed) |
| `../MyLife-Frontend/.env` | Frontend env — controls which backend to use |

---

## Development Modes

### Mode 1 — Frontend Only (Most Common)
> Use this when working on UI, components, or styling.
> No need to run Docker at all.

**`MyLife-Frontend/.env`**
```env
VITE_API_BASE_URL=https://myhealth.jo3.org
```

```bash
cd MyLife-Frontend
npm run dev
# Open http://localhost:3000
# All API calls go directly to your live EC2 backend
```

---

### Mode 2 — Full Local Stack
> Use this when adding new backend features, new API routes, or database changes.

**`MyLife-Frontend/.env`**
```env
VITE_API_BASE_URL=
```
> ⚠️ Leave this EMPTY so Vite proxy forwards to local Docker on port 80.

```bash
# Terminal 1 — Start local backend (no SSL)
cd MyLife-HealthCare
docker-compose -f docker-compose.local.yml up --build -d

# Terminal 2 — Start frontend
cd MyLife-Frontend
npm run dev
# Open http://localhost:3000
```

**Local request flow:**
```
Browser → localhost:3000/auth/login
         → Vite Proxy → localhost:80 (local NGINX)
                       → auth-service:8001
```

---

## Deployment

### Backend → EC2

**SSH into your EC2 instance and run:**
```bash
cd ~/MyLife-HealthCare-Backend

# Pull latest code
git pull

# Restart with production config (SSL enabled)
docker-compose down
docker-compose up --build -d

# Verify all containers are running
docker-compose ps

# Check gateway logs
docker logs mylife-gateway --tail 20
```

> ⚠️ Always use `docker-compose` (not `docker-compose.local.yml`) on EC2.

---

### Frontend → Vercel

```bash
cd MyLife-Frontend

# Commit your changes
git add .
git commit -m "your feature description"
git push
# Vercel auto-deploys on every push to main ✅
```

**Vercel Environment Variable (set once in Vercel dashboard):**
| Key | Value |
|---|---|
| `VITE_API_BASE_URL` | `https://myhealth.jo3.org` |

> Settings → Environment Variables → Add → Redeploy

---

## Testing Backend Connectivity

Run this script from any machine to verify the EC2 backend:
```bash
bash MyLife-HealthCare/test-backend.sh
```

**Or run manual curl checks:**
```bash
# Health check
curl https://myhealth.jo3.org/health

# Test login endpoint
curl -X POST https://myhealth.jo3.org/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"your@email.com","password":"yourpassword"}'

# Test CORS preflight
curl -X OPTIONS https://myhealth.jo3.org/auth/login \
  -H "Origin: https://my-life-health-care-frontend.vercel.app" \
  -H "Access-Control-Request-Method: POST" -i
```

---

## SSL Certificate

Certificates are stored on EC2 at:
```
/etc/letsencrypt/live/myhealth.jo3.org/fullchain.pem
/etc/letsencrypt/live/myhealth.jo3.org/privkey.pem
```

Copied into the project at (for Docker to read):
```
~/MyLife-HealthCare-Backend/certs/fullchain.pem
~/MyLife-HealthCare-Backend/certs/privkey.pem
```

**Renew certificate (every 90 days):**
```bash
# Stop Docker first (frees port 80)
docker-compose down

# Renew
sudo certbot renew

# Copy renewed certs
sudo cp -L /etc/letsencrypt/live/myhealth.jo3.org/fullchain.pem ~/MyLife-HealthCare-Backend/certs/
sudo cp -L /etc/letsencrypt/live/myhealth.jo3.org/privkey.pem ~/MyLife-HealthCare-Backend/certs/
sudo chown -R $USER:$USER ~/MyLife-HealthCare-Backend/certs

# Start Docker again
docker-compose up -d
```

---

## Quick Reference Cheat Sheet

| Task | Command |
|---|---|
| Start local frontend only | `npm run dev` (with `VITE_API_BASE_URL=https://myhealth.jo3.org`) |
| Start full local stack | `docker-compose -f docker-compose.local.yml up -d` + `npm run dev` |
| Deploy backend to EC2 | `git pull && docker-compose down && docker-compose up --build -d` |
| Deploy frontend | `git push` (Vercel auto-deploys) |
| View gateway logs | `docker logs mylife-gateway --tail 50` |
| Stop all local containers | `docker-compose -f docker-compose.local.yml down` |
| Test backend health | `curl https://myhealth.jo3.org/health` |
| Run full connectivity test | `bash test-backend.sh` |

---

## DNS Info

| DNS Server | Resolves `myhealth.jo3.org` to |
|---|---|
| Google (8.8.8.8) | ✅ `54.255.246.16` |
| Cloudflare (1.1.1.1) | ✅ `54.255.246.16` |
| Local ISP | May be cached — changes within 24-48 hrs |

**If a device can't reach the backend (ISP DNS lag), set its DNS to:**
- Primary: `8.8.8.8`
- Secondary: `1.1.1.1`
