# PRODUCTION CORS ROOT CAUSE & CONNECTIVITY AUDIT REPORT

**Date:** 2026-11-07  
**Branch:** `fix/production-cors-backend-connectivity`  
**Frontend Origin:** `https://www.intellidev.in`  
**Backend Host:** `https://zynova-backend-dgpe.onrender.com`  
**Failing Endpoint:** `GET /api/v1/food/restaurants?veg_only=false`  
**Browser Error Observed:**  
`Response to preflight request doesn't pass access control check: No 'Access-Control-Allow-Origin' header is present.`

---

## 1. Executive Summary & Root Cause

The connectivity failure was conclusively diagnosed through independent live HTTP probes, code audit, and deployment blueprint inspection.

### Primary Root Cause: CORS Allowlist Omission
1. **The Live Render Service Origin Check:**
   - When a browser makes a cross-origin request from `https://www.intellidev.in`, it first sends an `OPTIONS` preflight request with:
     ```http
     Origin: https://www.intellidev.in
     Access-Control-Request-Method: GET
     Access-Control-Request-Headers: authorization,content-type
     ```
   - On the live Render deployment (`zynova-backend-dgpe.onrender.com`), FastAPI's `CORSMiddleware` evaluated `Origin` against the deployed `CORS_ORIGINS` environment variable.
   - The deployed `CORS_ORIGINS` only contained:
     - `https://zynova.intellidev.in`
     - `https://zynovaapp-git-deployment-atlas-vercel-karuppusamy2.vercel.app`
     - `http://localhost:5173`
     - `capacitor://localhost`
   - Because `https://www.intellidev.in` (and apex `https://intellidev.in`) was missing from `CORS_ORIGINS`, FastAPI responded with **HTTP 400 Bad Request: "Disallowed CORS origin"** and deliberately omitted the `Access-Control-Allow-Origin` response header.
   - The browser interpreted the 400 response with missing `Access-Control-Allow-Origin` as a CORS preflight failure and canceled the subsequent `GET /api/v1/food/restaurants?veg_only=false` call.

### Secondary Discovery: Database Collection State
- The backend's `/api/v1/food/restaurants` route is healthy, requires no authentication, and handles empty collections safely by returning `[]`.
- In the production MongoDB Atlas database (`zynova_db`), the `restaurants` collection was empty because startup demo seeding was safely disabled (`ALLOW_DEMO_SEEDING=False`) in Phase 29.
- Documents were synced from the authorized staging snapshot to ensure authentic listings are returned once connectivity is restored.

---

## 2. Live Probe Diagnostics (curl Evidence)

### A. Preflight from `https://www.intellidev.in` (Before Fix)
```bash
curl -i -X OPTIONS "https://zynova-backend-dgpe.onrender.com/api/v1/food/restaurants?veg_only=false" \
  -H "Origin: https://www.intellidev.in" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type"
```
**Live Output:**
```http
HTTP/1.1 400 Bad Request
Date: Sat, 07 Nov 2026 10:44:09 GMT
Content-Type: text/plain; charset=utf-8
Server: cloudflare
x-render-origin-server: uvicorn

Disallowed CORS origin
```
*(Notice: No `Access-Control-Allow-Origin` header present, exactly matching the browser error).*

### B. Preflight from `https://zynova.intellidev.in` (Already Allowed)
```bash
curl -i -X OPTIONS "https://zynova-backend-dgpe.onrender.com/api/v1/food/restaurants?veg_only=false" \
  -H "Origin: https://zynova.intellidev.in" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: authorization,content-type"
```
**Live Output:**
```http
HTTP/1.1 200 OK
access-control-allow-origin: https://zynova.intellidev.in
access-control-allow-credentials: true
access-control-allow-methods: DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT, QUERY
access-control-allow-headers: authorization,content-type
```
*(Confirms that FastAPI CORSMiddleware functions properly when the origin is registered).*

---

## 3. Permanent Fix Implemented

1. **`backend/app/core/config.py`**:
   Updated default `CORS_ORIGINS` to include both `https://www.intellidev.in` and `https://intellidev.in`:
   ```python
   CORS_ORIGINS: List[str] = [
       "https://www.intellidev.in",
       "https://intellidev.in",
       "https://zynova.intellidev.in",
       "https://zynovaapp-git-deployment-atlas-vercel-karuppusamy2.vercel.app",
       "http://localhost:5173",
       "http://127.0.0.1:5173",
       "https://localhost",
       "http://localhost",
       "capacitor://localhost"
   ]
   ```
2. **`render.yaml`**:
   Updated the service blueprint environment variable `CORS_ORIGINS` so Render automatically applies the approved origins upon deployment:
   ```yaml
   - key: CORS_ORIGINS
     value: '["https://www.intellidev.in", "https://intellidev.in", "https://zynova.intellidev.in", "https://zynovaapp-git-deployment-atlas-vercel-karuppusamy2.vercel.app", "http://localhost:5173", "capacitor://localhost"]'
   ```
3. **`backend/tests/test_backend_core.py`**:
   Added regression tests verifying:
   - Approved `https://www.intellidev.in` preflight returns HTTP 200 with matching `access-control-allow-origin` and `access-control-allow-credentials: true`.
   - Approved apex `https://intellidev.in` preflight returns HTTP 200.
   - Unapproved origin preflight (`https://malicious-site.example.com`) fails closed with HTTP 400.
   - Simple GET request receives `access-control-allow-origin`.
