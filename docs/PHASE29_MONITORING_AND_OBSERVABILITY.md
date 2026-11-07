# PHASE 29 — MONITORING AND OBSERVABILITY

## 1. Structured Logging & Privacy
Backend logging formats messages using standard UTC timestamps and structured payloads (`%(asctime)s - %(name)s - %(levelname)s - %(message)s`).
- **Privacy Protections**: `sanitize_log_val` strips line breaks (preventing CRLF log forging) and automatically masks sensitive keys (`password`, `access_token`, `authorization`, `api_key`).

---

## 2. Health & Readiness Telemetry

| Endpoint | Target Component | Production Purpose |
| :--- | :--- | :--- |
| `GET /api/v1/health` | Process Liveness | Render/K8s liveness probe; verifies process is awake |
| `GET /api/v1/ready` | MongoDB + Redis Readiness | Traffic ingress gate; verifies database ping and Redis connectivity |
| `GET /api/v1/health/security`| Security Subsystems | Reports rate limiter status, token revocation cache, and KMS key ring health |
| `GET /api/v1/version` | Version Metadata | Reports application semantic version and deployment commit tracking |

---

## 3. Metrics & Alert Thresholds
- **HTTP 5xx Error Rate**: Alert triggered if 5xx errors exceed 1% over a 5-minute rolling window.
- **Database Latency**: P95 query response time exceeding 100ms indicates index degradation or Atlas IOPS throttling.
- **Rate Limit Hits (429)**: Spikes on `/auth/login` or `/auth/register` indicate credential-stuffing botnet attacks.
