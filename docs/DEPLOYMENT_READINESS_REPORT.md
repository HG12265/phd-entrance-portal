# Deployment Readiness Report - PhD Entrance Portal

This report summarizes server specs, deployment configuration, backup workflows, and QA verification details to prepare the PhD Entrance Portal for live exam day operations.

---

## 1. Architecture & Tech Stack

The portal is a high-performance web application optimized for concurrent exam delivery:
*   **Frontend**: React (served as optimized static assets via Nginx)
*   **Backend**: FastAPI (Python 3.10, served via Gunicorn with Uvicorn workers)
*   **Database**: MySQL 8.0 (configured with optimized performance indexes)
*   **Web Server / Ingress**: Nginx (serving static files, proxying API connections, and injecting security headers)

---

## 2. Server Specifications

To support **250+ concurrent candidates** and **800+ total candidates** comfortably:

### Minimum Recommended Specs:
*   **CPU**: 4 vCPU
*   **RAM**: 8 GB
*   **Storage**: SSD storage (at least 20 GB free)
*   **OS**: Ubuntu Server 22.04 LTS
*   **Software**: Docker Engine + Docker Compose

### Safer Recommended Specs (Ideal for Exam Day Headroom):
*   **CPU**: 8 vCPU
*   **RAM**: 16 GB
*   **Storage**: SSD storage (at least 40 GB free)

---

## 3. Production Environment Variables (.env)

The following env settings must be defined in `./backend/.env`:
*   `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`
*   `SECRET_KEY` (Generate strong hexadecimal random keys)
*   `ACCESS_TOKEN_EXPIRE_MINUTES` (admin JWT expiry)
*   `CANDIDATE_TOKEN_EXPIRE_MINUTES` (candidate JWT expiry)
*   `APP_ENV=production`
*   `CORS_ORIGINS` (Comma-separated host origins)
*   `MAX_UPLOAD_SIZE_MB` (upload size constraint)
*   `WEB_CONCURRENCY` (Gunicorn worker process concurrency limits)
*   `ENABLE_DOCS=false` (Swagger APIs block)

---

## 4. Docker Production Services

Deployed via `docker compose -f docker-compose.prod.yml up -d --build`:
*   `phd_mysql`: MySQL server listening on standard port 3306 (exposed internally, host port mapping disabled).
*   `phd_backend`: FastAPI app running behind Gunicorn worker processes.
*   `phd_nginx`: Static frontend server and ingress controller (ports 80/443 exposed). Serves candidate photographs directly via directory aliases.

---

## 5. Database & Uploads Backups

*   **Database Backup**: `python scripts/backup_database.py` generates timestamped SQL dumps inside `backups/database/` safely.
*   **Uploads Archive**: `python scripts/backup_uploads.py` zips candidate photographs and spreadsheet logs to `backups/uploads/`.
*   **Recovery Operations**: Restorations can be handled in minutes using docker cp and mysql shell tools (see [restore_database_notes.md](file:///c:/Users/Gowtham/Desktop/phd-entrance-portal/backend/scripts/restore_database_notes.md)).

---

## 6. Known Limitations

> [!WARNING]
> *   **Tamil Font Rendering**: ReportLab PDF exports depend on standard font libraries. If Unicode Tamil fonts are missing on the host environment, Tamil characters may render as square brackets.
> *   **Print Fallback**: To bypass any font limits, a highly polished browser-level print-friendly candidate report layout is available. Administrators can click "Print Report" inside their browser to print/save as PDF directly.
> *   **Load Testing**: While test scripts are ready in `load_tests/`, load testing should be performed on a production-like test machine before the real exam day to verify local hosting network capacity.

---

## 7. Security Hardening Checklist
*   [x] JWT token scopes for admins and candidates are checked separately.
*   [x] Wildcard CORS is disabled in production.
*   [x] Swagger / OpenAPI docs are disabled in production unless `ENABLE_DOCS=true`.
*   [x] Path traversal checks sanitize uploaded photo filenames.
*   [x] Password attributes and secret keys are completely stripped from backend logs.
*   [x] Server signature tokens are hidden in Nginx responses.
