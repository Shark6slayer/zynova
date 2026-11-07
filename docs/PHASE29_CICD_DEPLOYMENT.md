# PHASE 29 — CI/CD AND DEPLOYMENT PIPELINE

## 1. Automated Workflow Pipeline (`.github/workflows/production-ci.yml`)
The continuous integration pipeline validates every pull request and push to release branches:
1. **Backend Test & Lint**: Runs pytest suite across all 176 test cases, checking auth, rate limiting, and integrations with zero tolerance for regressions.
2. **Frontend Typecheck & Build**: Runs `tsc -b && vite build` verifying bundle integrity and chunk budgets.
3. **Automated Secret Scanner**: Scans repository text and code for leaked API keys, tokens, and private keys before permitting merge.

---

## 2. Production Deployment Specification (`render.yaml`)
- **Backend Service**: Configured on Render PaaS (`python` environment).
- **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- **Health Path**: `/api/v1/health`
- **Zero-Downtime Deploy**: Rolling container updates ensure seamless traffic handoff during updates.
- **Rollback Runbook**: If health checks fail during deployment, Render cancels the update and routes traffic to the previous healthy container.
