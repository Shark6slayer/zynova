# PHASE 29 — BACKUP AND DISASTER RECOVERY SPECIFICATION

## 1. Objectives & Targets
- **Recovery Point Objective (RPO)**: $\le 1\text{ hour}$ for database state; $\le 24\text{ hours}$ for uploaded media.
- **Recovery Time Objective (RTO)**: $\le 30\text{ minutes}$ for application traffic restoration.

---

## 2. Backup Strategy

### 2.1 Database (MongoDB Atlas)
- **Continuous Backups**: Atlas point-in-time recovery enabled with 7-day retention.
- **Daily Snapshots**: Automated daily snapshots retained for 30 days across multiple geographic regions.
- **On-Demand Dumps**: Standard `mongodump` utility used for pre-deployment rollback snapshots.

### 2.2 Media Assets (Cloudflare R2 / S3)
- **Object Versioning**: Enabled on media storage bucket to prevent accidental overwrite or premature deletion.
- **Lifecycle Rules**: Unconfirmed uploads in temporary quarantine purged after 48 hours.

---

## 3. Disaster Recovery Runbook
1. **Database Corruption / Loss**:
   - Access Atlas Console -> Restore Snapshot to target timestamp.
   - Update `MONGODB_URI` environment variable in Render if a new cluster URI was provisioned.
2. **Compute Service Outage**:
   - Deploy backend codebase to secondary region or backup provider using `render.yaml` or Docker container definitions.
   - Point Cloudflare DNS records to the secondary backend origin.
