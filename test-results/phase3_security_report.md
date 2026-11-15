# Zynova Phase 3 — Application Security & Integration Audit Report

**Date of Execution**: 2026-10-18T10:15:00+05:30  
**Target Origin (Frontend)**: `https://zynova.intellidev.in` (Production Read-Only)  
**Target Origin (Backend)**: `https://zynova-backend-dgpe.onrender.com` (Production Read-Only Probe)  
**Local Test Environment**: ASGI in-process transport with local MongoDB (`127.0.0.1:27017/super_ai_db`)  

---

## 1. Security Baseline & Vulnerability Findings

### Finding 1: Backend .env Directory-Dependent CORS Configuration Mismatch
- **Severity**: Low (Developer/Test Environment Gotcha; Production is Safe)
- **Component**: `backend/.env` vs `backend/app/core/config.py`
- **Evidence**:
  - `backend/app/core/config.py` defines `CORS_ORIGINS` default containing `"https://zynova.intellidev.in"`.
  - When tests or commands are run directly inside `c:\super_ai\backend`, Pydantic loads `backend/.env`, where `CORS_ORIGINS` omitted `"https://zynova.intellidev.in"`.
  - Production Render environment variables explicitly configure `https://zynova.intellidev.in` and returned HTTP 200 with the correct CORS headers.
- **Impact**: Tests executing from the `backend/` subfolder failed preflight tests, while tests executed from the project root passed.
- **Remediation**: Align `backend/.env.example` and local `.env` templates so developers running tests inside `backend/` do not experience false CORS preflight rejections.

---

### Finding 2: Unmaintained Passlib Argon2 Deprecation on Python 3.13
- **Severity**: Medium (Maintainability / Technical Debt)
- **Component**: `passlib.handlers.argon2`
- **Evidence**: Every pytest suite outputs:
  ```text
  DeprecationWarning: Accessing argon2.__version__ is deprecated and will be removed in a future release.
  Use importlib.metadata directly to query for argon2-cffi's packaging metadata.
  ```
- **Impact**: When upgrading to Python 3.14+, `argon2.__version__` will raise `AttributeError`, breaking password hashing if unaddressed.
- **Remediation**: Migrate from legacy `passlib` to direct `argon2-cffi` PasswordHasher prior to the Python 3.14 lifecycle.

---

### Finding 3: Free-Form String Acceptance in User Preference Theme
- **Severity**: Low
- **Component**: `app/schemas/all_schemas.py` (`PreferencesModel.theme`)
- **Evidence**: The `theme` field in `PreferencesModel` is typed as a generic `str` without an enum or regex restriction. While the backend strictly serves `application/json` (preventing server-side XSS injection), arbitrary strings are stored in MongoDB.
- **Impact**: Storing arbitrary strings in the theme field allows arbitrary client theme state storage.
- **Remediation**: Constrain `theme` in Pydantic schema to an enum or allowed set (e.g. `midnight-glass`, `amber-glow`, `emerald-dark`).

---

## 2. Authorization & Data Boundary Verification

| Boundary Test | Verification Method | Outcome |
| :--- | :--- | :--- |
| **Tampered / Expired JWT** | Injected signature-tampered and negative-expiry tokens into `/api/v1/auth/me` | **PASSED** (HTTP 401/403) |
| **Cross-User Chat Eavesdropping** | User C (Eve) attempted to read conversation messages between User A and User B | **PASSED** (HTTP 401/403/404, Zero Message Leakage) |
| **Cross-User Shopping Orders** | User B attempted to read or cancel User A's orders | **PASSED** (HTTP 400/404, Strict Customer ID Isolation) |
| **NoSQL Object Injection** | Injected `{"$ne": null}` into JSON login body | **PASSED** (HTTP 400/422 Schema Validation Rejection) |
| **Payment Account Masking** | Queried linked bank accounts via `/api/v1/payments/accounts` | **PASSED** (Full account number stripped, only `••••76` returned) |

---

## 3. Production Read-Only Safety Confirmation
- Read-only probes performed against:
  - `https://zynova.intellidev.in/` (HTTP 200, strict HTTPS, clean console)
  - `https://zynova-backend-dgpe.onrender.com/api/v1/health` (HTTP 200, `healthy`)
  - `https://zynova-backend-dgpe.onrender.com/` (HTTP 200, `operational`)
- **Zero mutations or deployments occurred on production.**
