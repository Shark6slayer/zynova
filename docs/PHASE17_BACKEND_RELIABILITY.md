# PHASE 17 — BACKEND RELIABILITY AND HOSTING ARCHITECTURE

**Document Reference:** `ZYNOVA-DOC-PHASE17-BACKEND-RELIABILITY`  
**Execution Timestamp:** 2026-11-07T09:50:00+05:30  
**Evaluator:** Principal DevOps Engineer & Cloud Systems Architect  

---

## 1. RENDER COLD-START BEHAVIORAL INVESTIGATION

### Empirical Evidence:
- **Dormant State (Inactivity > 15 mins):** Render suspends the container process. An incoming HTTP request initiates a spin-up cycle.
- **Observed Initial Wake Latency:** First request timed out at 10,000ms. Subsequent retry with a 35s timeout resolved in **32.4 seconds**.
- **Warmed Latency:** Once initialized, subsequent API requests measured:
  - `/api/v1/health`: **476.96ms**
  - `/api/v1/ready`: **991.94ms**
  - `/api/v1/health/security`: **1045.82ms**
- **Impact on End Users:** High abandonment risk during initial app launch if the backend is dormant.

---

## 2. PRODUCTION HOSTING COMPARISON MATRIX

| Dimension | Render Free Tier (Current) | Render Starter (Recommended) | Railway Hobby / Pro | AWS ECS Fargate | Hetzner Cloud VPS (Docker) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Monthly Cost** | **$0.00** | **$7.00 / month** | $5.00 – $10.00 / mo | $15.00 – $35.00 / mo | **€4.50 (~$4.90) / mo** |
| **CPU Allocation** | 0.5 shared vCPU | 0.5 dedicated vCPU | 1.0–2.0 shared vCPU | 0.5–1.0 vCPU | **2 dedicated vCPUs** |
| **RAM Allocation** | 512 MB | **512 MB (Persistent)**| 512 MB – 2 GB | 1 GB – 2 GB | **4 GB RAM** |
| **Idle Behavior** | **Sleeps after 15m** | **Always On (0 cold starts)** | Always On | Always On | Always On |
| **Deployment Flow** | Git push / Webhook | Git push / Webhook | Git push / Nixpacks | ECR + Task definition | Git push + Docker Compose |
| **Built-in SSL / CDN**| Automated Let's Encrypt | Automated Let's Encrypt | Automated Cloudflare | AWS ALB + ACM | Traefik / Nginx reverse proxy |
| **Multi-Worker Scaling**| Single process | Single worker | Horizontal scaling | Auto-scaling groups | Horizontal Docker swarm |

---

## 3. INFRASTRUCTURE RECOMMENDATION

1. **Short-Term (Immediate / 0 migration effort):**
   - Upgrade the current Render service `zynova-backend-dgpe` to the **Starter Plan ($7/mo)**.
   - This eliminates 100% of cold starts without requiring DNS updates or environment re-provisioning.
2. **Medium-Term (Scale Phase):**
   - Migrate to a dedicated **Hetzner Cloud VPS (CPX21 - €8/mo)** running Docker Compose with Uvicorn (4 workers), a local Redis cache, and Traefik reverse proxy.
   - This provides 8x more RAM and 4x more CPU for equivalent cost.

