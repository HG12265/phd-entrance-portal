# PhD Entrance Exam Portal

A robust, enterprise-grade entrance examination system for PhD candidates. Designed with multi-lingual support (English & Tamil), scientific/mathematical formula rendering, Excel administration interfaces, and containerized deployment structures.

---

## Tech Stack
* **Frontend**: React.js (Vite, JavaScript), React Router DOM (v7), Axios
* **Backend**: Python FastAPI
* **Database**: MySQL (v8.0)
* **ORM**: SQLAlchemy
* **Excel Processing**: Pandas, OpenPySQL
* **Security & Tokens**: Passlib (Bcrypt), Python-JOSE (JWT)
* **Deployment**: Docker & Docker Compose

---

## Completed Phase 1 Features
1. **Frontend Architecture**:
   * Scaffolding of React Vite structure in `./frontend`.
   * Complete route management with `react-router-dom` for candidate workflows (`/`, `/candidate/login`, `/candidate/profile`, `/candidate/instructions`, `/candidate/exam`, `/candidate/result`) and admin consoles (`/admin/login`, `/admin/dashboard`, `/admin/candidates`, `/admin/questions`, `/admin/reports`).
   * Clean styling in `index.css` implementing responsive layout, sidebars, dashboard grid metrics, tables, alerts, and custom exam question palette.
   * Role-based routing guards (`ProtectedRoute.jsx`) leveraging local storage tokens.
2. **FastAPI Backend Structure**:
   * Server entry point (`main.py`) with title `"PhD Entrance Exam Portal API"`.
   * Cross-Origin Resource Sharing (CORS) enablement for UI integrations.
   * Modular routing architecture representing Admin, Candidate, Department, Question, and Exam routers.
3. **Database Connection & Schemas**:
   * PyMySQL engine configuration with SQLAlchemy.
   * Environment variable config loader (`config.py`) parsing `.env`.
   * Full skeleton schemas for `AdminUser`, `Department`, `Candidate`, `Question`, `Exam`, `ExamAttempt`, and `CandidateAnswer`.
   * Database initialization script (`database/init.sql`) with explicit UTF-8 (`utf8mb4`) and collation settings to support Tamil translations, integration formulas (e.g. `∫`), and subscripts/superscripts (e.g. `x²`).
4. **Docker Configurations**:
   * Multi-container composition (`docker-compose.yml`) declaring:
     * **`mysql`**: Image `mysql:8.0`, exposing port `3307` externally, setting up `utf8mb4` schemas, and running `init.sql` automatically.
     * **`backend`**: Exposes FastAPI on port `8000`.
     * **`frontend`**: Exposes Vite dev-server on port `5173`.

---

## Completed Phase 2 Features
1. **Admin Authentication**:
   * Secure admin login endpoint `/api/admin/auth/login` returning bearer JWT access token.
   * Protected `/api/admin/auth/me` returning authenticated user profile details.
   * Password hashing using bcrypt.
   * `get_current_admin` auth dependency that decodes JWT, queries database, and rejects inactive users.
2. **Default Admin Seeding**:
   * Seeding script `backend/scripts/create_default_admin.py` to securely insert initial super administrator account.
3. **Department Management CRUD**:
   * Full database support with constraints for `Department` schema in SQLAlchemy.
   * Protected routes under `/api/admin/departments`:
     * `GET /`: Lists all departments ordered by name.
     * `GET /{id}`: Gets single department.
     * `POST /`: Validates and creates a new department (uniqueness checks).
     * `PUT /{id}`: Modifies department attributes.
     * `DELETE /{id}`: Deactivates department (soft delete).
4. **Department Seeding**:
   * Seeding script `backend/scripts/seed_departments.py` to batch-populate the 30 base departments.
5. **Frontend Integrations**:
   * Refined route guards on frontend using `admin_token`.
   * Built interactive `DepartmentManagement.jsx` page with list, creation, and updating modules.
   * Linked real department counts to the admin Dashboard view.

---

## Completed Phase 3 Features
1. **Candidate Database Schema & Import Logs**:
   * Created standard Pydantic validation schemas.
   * Defined Candidate model fields including `application_number`, `dob`, `mobile_number`, `applied_subject`, `photo_filename`, `photo_path`, `photo_status`, and `import_batch_id`.
   * Created `import_logs` model and logger database tables.
2. **Excel Validation & Parsing Engine**:
   * Created validation utilities to handle columns case-insensitively and normalize spaces.
   * Added robust DOB parser supporting standard string formats (e.g. `DD-MM-YYYY`, `DD/MM/YYYY`, `YYYY-MM-DD`) and Excel numeric date formats.
   * Added duplicate checkers mapping Excel application number rows to prevent duplicates in the same upload batch or already existing db entries.
   * Maps candidate `Applied Subject` to corresponding `Department` dynamically using code or name mappings.
3. **Photo Management & Folder Remapping**:
   * Maps uploaded photos to candidate files automatically by replacing `/` with `-` (e.g. `CET/PHD/J26/0123` matches to `CET-PHD-J26-0123.JPG`).
   * Supported extensions: `.jpg`, `.jpeg`, `.png`, `.JPG`, `.JPEG`, `.PNG`.
   * Built `remap-photos` scan function to query the storage folder and auto-rebind orphan photo assets to database candidate files.
4. **Static File Serving**:
   * Configured FastAPI server to mount and serve uploads directory safely at `/static/candidate_photos`.
5. **Frontend Views & Dashboards**:
   * **Candidate Upload Page (`CandidateUpload.jsx`)**: Split-form layout for spreadsheet uploads and batch photo uploads, showing error row reports and mapping logs.
   * **Candidate Registry List (`CandidateList.jsx`)**: Searchable list with paging controls, department filter, and photo status filter.
   * **Candidate Details Panel (`CandidateDetails.jsx`)**: Full student profile inspector page displaying candidate photo or missing placeholder card.
   * **Live Dashboard Counts**: Synchronized Candidate total counts and Missing Photo statistics dynamically with the admin homepage.

## Completed Phase 4 Features
1. **Department-Wise Question Bank Ingestion**:
   * API endpoints under `/api/admin/questions` to handle Excel uploading per department.
   * Enforces the **70-question rule**: accepts uploads only if the spreadsheet contains exactly 70 valid, non-duplicate MCQ questions.
   * `replace_existing` logic: if `replace_existing=true`, soft-deactivates (`is_active=False`) previous questions for that department in the database to prevent duplicate active banks while preserving history.
2. **Spreadsheet Normalization & Column Validation**:
   * Utility parser to process headers case-insensitively and trim spaces.
   * Accept variations like `Question No`, `Q.No`, `Question Text`, `Option A`, `Correct Option` (A/B/C/D), `Marks`.
   * Maps correct options (A, B, C, D, lowercase, or numeric 1-4 to A-D) and handles marks default fallback to 1.
3. **Tamil and Formula/LaTeX Formatting Support**:
   * Full Unicode character safety inside MySQL (`utf8mb4`) and FastAPI JSON responses to serve Tamil characters and custom math symbols.
   * Integrated `better-react-mathjax` on React frontend to parse and render inline math LaTeX formulas encapsulated in `( ... )`.
4. **Admin UI Panels**:
   * **Question Upload Page (`QuestionUpload.jsx`)**: Dropdown department select, live question bank readiness indicator, template download link, replace-existing checkbox, and row validation error log report.
   * **Question Registry List (`QuestionBank.jsx`)**: Searchable index of all questions with filters for department, keyword matching on text/choices, and soft-delete capabilities.
   * **Question Preview Page (`QuestionPreview.jsx`)**: Exam-style rendering for all 70 department questions, highlighting correct options and solutions, with print-ready CSS layout.
5. **Dashboard Counts**:
   * Added dynamic count of "Question Banks Ready" (active departments with exactly 70 questions).

---

## Completed Phase 5 Features
1. **Candidate Login & Authentication**:
   * Login route `/api/candidate/auth/login` validating Application Number and DOB (accepts `DD-MM-YYYY`, `DD/MM/YYYY`, `YYYY-MM-DD`). Returns generic errors only.
   * Token generation with payload properties `sub` (application number), `candidate_id`, and `role: candidate`.
   * Current profile route `/api/candidate/auth/me` to safely load student parameters.
2. **Admin Exam Session Scheduling**:
   * SQLAlchemy schema representation for multiple exam sessions (`ExamSession` mapping table `exam_sessions`).
   * Soft deactivation, date filters, validation against duplicate session names per date, and custom guidelines.
3. **Database Migration Script**:
   * Isolation script `backend/scripts/migrate_phase5.py` to create tables, check if columns exist, and alter target schemas without data loss.
4. **Timezone-Aware Guards & Enter Exam Lock**:
   * Time comparisons matched using local `Asia/Kolkata` timezones.
   * Access to `/candidate/exam` is locked on load by hitting `POST /api/candidate/exam/enter` immediately, redirecting unauthorized candidates to instructions with active backend error messages.
5. **Session Resolution**:
   * If a candidate has an assigned session, it is fetched. If inactive, access is denied. If unassigned and exactly one active session exists, it resolves automatically. If multiple active sessions exist, it blocks access until mapped.
6. **Frontend Enhancements**:
   * Separation of `admin_token` and `candidate_token` request interceptors in Axios instance.
   * **Instructions Page (`Instructions.jsx`)**: Displays schedules, timezone-aligned dates, custom instructions, and polls status every 10 seconds. Renders state banners: green for live, yellow for waiting, red for ended, and gray for no session.

---

## Completed Phase 6 Features
1. **Exam Attempt & Answer Schemas**:
   * Isolated schemas for `ExamAttempt` and `CandidateAnswer` with candidate-session indexes and answer progress tracks (`not_visited` as default status).
2. **Safe Migration Logic**:
   * Migration script `backend/scripts/migrate_phase6.py` checks incompatibilities, generates data backups of current tables if present, drops schemas, and rebuilds safely.
3. **Randomized Question Shuffling**:
   * Shuffles questions on first login per candidate attempt using `secrets.SystemRandom().shuffle()`, saving order arrays as JSON.
4. **Timezone-Aware Expiry Commit**:
   * Updates state to `expired` on DB if current backend `Asia/Kolkata` time crosses attempt end limits.
5. **MCQ Auto-Saving**:
   * Save choices immediately to `/api/candidate/exam/save-answer`, strictly blocking correctness metrics (`correct_option`, `answer`, `is_correct`, `mark_awarded`) in API requests/responses.
6. **Interactive Navigation Panel**:
   * Premium UI with a 70-question grid showing color states (Answered = green, Not answered = red, Flagged = yellow, Answered and flagged = yellow with green border, Not visited = white).
7. **First View Status Updates**:
   * Triggering `/mark-status` to shift state from `not_visited` to `not_answered` automatically on navigate.
8. **Timer Resync**:
   * 30-second interval updates to prevent client clock lag. Lock controls and disabled input on expiry.

---

## Completed Phase 7 Features
1. **Exam Submission**:
   * API endpoints for `POST /submit` and `GET /result` with router tags.
   * Enables manual and automatic exam submissions.
2. **Backend Score Calculation Service**:
   * Scoring service parses candidate answers, checks choices against correct options, registers pass-fail status (threshold = 28/70), and commits updates in a single transaction.
3. **Attempt Lock**:
   * Blocks subsequent answer updates, navigations, or status modifications once final results are computed.
4. **Timezone-Aware Expiry Auto-Finalization**:
   * Backend automatically triggers auto-evaluation and shifts state to `auto_submitted` if checks to `/current`, `/save-answer`, or `/timer` arrive after attempt expiry.
5. **Security Verification**:
   * Candidate result summary strictly excludes correct option mappings, question keys, or explanations.
6. **Result Page Display**:
   * Renders Candidate Profiles, obtained score metrics, correct/wrong/unvisited counters, PASS/FAIL badges, and submission type labels.

---

## Completed Phase 8 Features
1. **Admin Report Dashboard**:
   * Professional reporting dashboard showing metrics: total candidates, appeared count, absent count, passed, failed, pass percentage, average score, and highest/lowest scores.
2. **Subject Breakdown Summary**:
   * Department subject-wise statistics table showing registered, appeared, absent, passed, failed, average scores, and question bank readiness status.
3. **Overall & Subject-wise Leaderboards**:
   * Leaderboards sorted by score DESC, correct_count DESC, submitted_time ASC, and application_number ASC. Full pagination support.
4. **Absentees Logs**:
   * Lists active candidates who have not submitted exam attempts for the selected session.
5. **Individual Candidate Answer Report**:
   * Review question-wise answers with candidate choices, correct choices, status, and marks. Supports print-friendly formats.
6. **Excel & PDF Exports**:
   * Excel export buttons for overall, subject, and absentees list. Candidate report card PDF generation using ReportLab. Safe filename conversions.

---

## Completed Phase 9 Features
1. **Production Configuration**: Environment files example structures for both backend and frontend (`.env.example`) specifying DB, JWT timeouts, upload sizing limits, configurable gunicorn worker options (`WEB_CONCURRENCY`), CORS allowed origins list, and Swagger docs controller (`ENABLE_DOCS=false`).
2. **Nginx Reverse Proxy Ingress Config**: Restricts direct MySQL public port exposures, custom size limits (`client_max_body_size 100M;`), secure proxy timeouts, Gzip compressions, and server signature hide.
3. **Multi-Stage Docker Prod Build**: Structured `docker-compose.prod.yml` building react static components, running FastAPI backend Gunicorn-Uvicorn worker nodes, health checks (MySQL status/backend endpoints checks), and shared volumes.
4. **Performance Indexing Optimizer**: Safely check and add non-duplicate, repeat-safe indices (`migrate_phase9_indexes.py`) to candidates, questions, attempts, answers, sessions, and departments tables.
5. **Rotating Logging Configuration**: Configures rotating log formats for `app.log`, `error.log`, and `exam_events.log`. Securely logs events (login, exam start, save failures, final submits, exports) omitting credentials, full DOBs, or correct option explanations.
6. **Emergency Backup Utilities**: Created db dump (`backup_database.py`), upload files zip (`backup_uploads.py`), and restoration scripts recovery logs ([restore_database_notes.md](file:///c:/Users/Gowtham/Desktop/phd-entrance-portal/backend/scripts/restore_database_notes.md)).
7. **Locust Stress Testing Simulation**: Developed custom load simulation set (`locustfile.py`) tracking login attempts, details retrieval, instructions views, attempts starts, save choices loops, and submits.
8. **Deployment Reports & Ready Checklist**: Formulated timeline checklists ([EXAM_DAY_CHECKLIST.md](file:///c:/Users/Gowtham/Desktop/phd-entrance-portal/docs/EXAM_DAY_CHECKLIST.md)) and full server reports ([DEPLOYMENT_READINESS_REPORT.md](file:///c:/Users/Gowtham/Desktop/phd-entrance-portal/docs/DEPLOYMENT_READINESS_REPORT.md)).

---

## Completed Phase 10 Features
1. **Administrative Hard Delete Controls**:
   * Complete cascaded delete handlers for Departments, Candidates, Question Banks, and Exam Sessions.
   * Restricts candidate actions on administrative cleanup operations.
2. **Manual Candidate Registration**:
   * Enabled direct additions of single candidate entries from the Admin Dashboard, with format validations for DOB, Subject mapping, and unique constraints.

---

## Completed Phase 11 Features
1. **Full Screen Exam Mode**:
   * Automatic fullscreen request via `documentElement.requestFullscreen()` on entering `ExamPage.jsx`.
   * Displays persistent fullscreen status badge: `"🟢 Full Screen: Active"` or `"🔴 Full Screen: Not Active"`.
   * Warning overlay covers screen if fullscreen exits, locking out option selections and review button actions until full screen is restored.
   * Logs fullscreen entry/exit event sequences directly to the backend database audit logger `/api/candidate/exam/fullscreen-event`.
2. **Device / Browser Lock & Admin Resume Controls**:
   * Uses client fingerprints (`localStorage` token `exam_client_id`) linked to exam attempt.
   * Multi-device logins or cross-browser switches trigger `423 Locked` block responses. Same-browser tabs refresh and resume normally.
   * Admin consoles (`/admin/exam-control`) search candidates by application number to inspect attempt parameters (remaining time, counts, lock status).
   * Confirmations dialog overrides the device locks safely without resetting candidate answers, timers, question shuffling order, or scores.
   * Block candidate logins and attempt rewrites on completed or time-expired attempts with `403 Forbidden` response.

---

## Completed Phase 12 Features
1. **Official Periyar Candidate Excel Support**:
   * Auto-detects header row in the first 20 rows by checking for at least 4 recognized columns.
   * Extracts new Candidate database fields: `application_id`, `applicant_name`, `initial`, `category_ft_pt`, `programme_offered`, `subject`, and `original_department_text`.
   * Integrates backward compatibility by retaining old Excel formatting capabilities.
2. **Dynamic Department Resolution**:
   * Dynamic fallback checking of Department name, Code, Subject column, case-insensitive trimmed, and substring contains matching.
   * Explicit alias dictionary to map common Excel department variations (e.g. `"Food Science Technology and Nutrition"` maps to `"Food Science and Nutrition"`).
3. **Flexible Candidate Photo Lookup**:
   * Resolves photo mappings using multiple naming format patterns (e.g., handles hyphenated vs. non-hyphenated prefixes: `CETPHD-J26-0128` / `CET-PHD-J26-0128` / `CET-PHD-J26-0128.JPG`).
4. **Enhanced Candidate Login & Admin Console**:
   * Unified Authentication querying against both `application_id` and `application_number`.
   * Complete update to candidate manual forms, registry listings with Category and Session dropdown filters, profile lists, and detail panels.
5. **Leaderboard and Absentees Reports**:
   * Excel export spreadsheets rewritten to output all new candidate schema columns.
---

## Completed Phase 13 Features
1. **Prevent Re-exam After Submit**:
   * Implemented completed-attempt checks on candidate entry, status checks, and start queries to block logins or start attempts if an official submitted/auto-submitted attempt already exists.
2. **Submit Route Idempotency**:
   * Candidate `/submit` endpoint returns the existing submission summary on resubmit and rejects duplicate in-progress attempts by invalidating them.
3. **Leaderboard and Reports Deduplication**:
   * Integrated a query filter that limits leaderboard lists, statistics, and absentees to only the earliest official completed attempt per candidate per session.
4. **Duplicate Cleanup Script**:
   * Script `fix_duplicate_attempts_phase13.py` retroactively invalidates duplicate attempts in the database.

---

## Completed Phase 14 Features
1. **Admin Force Reopen for Submitted Attempts**:
   * Admin can force-reopen a previously submitted/auto-submitted attempt back to `in_progress`.
   * Restores the remaining exam duration at the submit moment timezone-safely from `remaining_seconds_at_submit`.
   * Existing question shuffle order and previously selected candidate answers are preserved.
2. **Audit Logging Trail**:
   * Logs every reopen action in `exam_attempt_reopen_audits` including admin ID, candidate ID, old status, new status, old score, old end time, old submitted time, remaining seconds, and administrative reason.
3. **Search candidate UI and Backend Enhancements**:
   * Improved the search input form on the Admin console with larger text inputs (46px height), responsive layouts, a "Clear" button, empty input validations, and Enter key bindings.
   * Search queries resolve case-insensitively and space-trimmed against both `application_number` and `application_id`.

---

## Local Setup Instructions

### 1. Running Backend Locally
Ensure you have Python 3.9+ and dependencies installed.
```bash
# Navigate to backend directory
cd backend

# Create local virtual environment and activate it (optional but recommended)
python -m venv venv
venv\Scripts\activate  # On Windows
source venv/bin/activate  # On Unix/macOS

# Install dependencies
pip install -r requirements.txt

# Start FastAPI server
uvicorn app.main:app --reload
```

### 2. Creating Default Admin & Seeding Departments
Make sure you run these from the `backend` directory:
```bash
# Create default administrator and ensure all database schemas are created
python scripts/create_default_admin.py

# Seed base departments
python scripts/seed_departments.py

# Run Phase 5 database migration script (updates candidate columns and creates sessions table)
python scripts/migrate_phase5.py

# Run Phase 6 database migration script (creates attempts and answers tables, handles safe backups)
python scripts/migrate_phase6.py

# Run Phase 7 database migration script (adds missing score columns dynamically to existing tables)
python scripts/migrate_phase7.py

# Run Phase 12 database migration script (adds official candidate columns and populates application_id)
python scripts/migrate_phase12_candidate_fields.py
```

### 3. Running Frontend Locally
Ensure you have Node.js installed.
```bash
# Navigate to frontend directory
cd frontend

# Install package dependencies
npm install

# Start Vite dev server
npm run dev
```
Open [http://127.0.0.1:5173](http://127.0.0.1:5173) in your browser.

### 4. Running via Docker (Complete Stack)
Make sure you have Docker Desktop running.
```bash
# Run from the project root directory
docker-compose up --build
```
This builds and runs all services in the background.

---

## API & Login Testing Reference

### Default Admin Credentials:
* **Email**: admin@phdportal.com
* **Password**: Admin@123

### Sample Candidate Excel Headers:
`Name` | `Application Number` | `Mail ID` | `Applied Subject` | `DOB` | `Mobile Number`

### Photo Filename Mapping Rule:
`CET/PHD/J26/0123` → `CET-PHD-J26-0123.JPG`

### Sample Question Excel Columns:
`Question No` | `Question Text` | `Option A` | `Option B` | `Option C` | `Option D` | `Correct Option` | `Marks`

### LaTeX Formula Examples:
* Inline formula: `( E = mc^2 )`
* Fractions: `( \frac{x+y}{z} )`
* Integral: `( \int x^2 dx )`
* Scientific notation: `6.022 \times 10^{23}`

### Live Testing Steps:
1. Log in as Admin at the Login Screen.
2. Go to **Question Upload** page.
3. Download the Excel template using the "Download Excel Template" button.
4. Select a department from the dropdown (e.g. Computer Science).
5. Attempt uploading a file with less than 70 questions or duplicate numbers to see error logs.
6. Upload a valid 70-question Excel spreadsheet.
7. Click "Preview Current Questions" to inspect the rendering.
8. Verify that Tamil text, Unicode symbols, and LaTeX equations render properly.
9. Try re-uploading the same file without checking the "Replace existing" box to verify security blocks, then toggle it to overwrite.
10. Verify Phase 5 Candidate Workflows:
    * Log in as Admin and navigate to **Exam Sessions** to configure a new session (e.g. set start time to 2 minutes in future).
    * Import a test candidate (or verify an existing one) and map their `exam_session_id` or leave it null to test auto-resolving.
    * Log in as the Candidate using application number and DOB. Verify profile details and photograph render correctly.
    * Proceed to instructions; verify that the "Start Exam Now" button is disabled and shows the yellow "waiting" banner.
    * Attempt accessing `/candidate/exam` directly by updating browser URL; ensure the backend guard intercepts, rejects access, and redirects back to instructions showing the error block.
    * Wait for the scheduled start time; confirm status banner turns green and the button becomes enabled.
    * Click "Start Exam Now" and verify redirection to the verified exam room placeholder.
    * Click Logout and confirm security tokens are wiped from cache.
11. Verify Phase 6 Live Exam Features:
    * Log in as Admin and verify that candidate's department has exactly 70 active questions.
    * Log in as Candidate, enter the live exam, and confirm the 70 questions are successfully loaded and shuffled.
    * Inspect the browser Network tab; confirm that `correct_option` or `answer` is never sent in candidate responses.
    * Select answers; confirm that the save status indicator displays auto-saving updates.
    * Toggle "Mark for Review" and clear response; verify that colors update correctly in the sidebar palette.
    * Refresh the page; verify that shuffled order, timer state, and selections are fully restored from the backend.
    * Confirm that submitting is disabled with the notice: *"Submit will be enabled in Phase 7"*.
    * Confirm that once the time is over, saving is blocked and the page locks candidate choices.
12. Verify Phase 7 Evaluation & Results:
    * Log in as Candidate, enter the live exam, choose some answers, and click "Submit Examination".
    * Confirm confirmation dialogue alerts.
    * Proceed to submit; verify immediate redirect to `/candidate/result`.
    * Inspect score card, correctness counts, pass/fail thresholds, and submitted time.
    * Attempt back-navigation or re-logging; verify that re-starting or changing answers is locked, and candidate is redirected to result page.
    * Log in as a Candidate in a different browser, allow attempt timer to elapse, and confirm that the frontend auto-submits, or that the backend commits final state as `auto_submitted`.
13. Verify Phase 8 Admin Reports & Analytics:
    * Log in as Admin and navigate to **Reports** dashboard in sidebar menu.
    * Verify stats cards and subject summary tables load.
    * Verify overall leaderboard, subject leaderboard, and absentees list tabs.
    * Test filters: change session dropdown, department dropdown, result status, and text search input.
    * Click "Review" on any candidate record to view the question-by-question candidate report card.
    * Verify that correct answers and choices are visible to Admin on this page.
    * Click "Print Report" to check formatting, or click "Download PDF" to fetch the ReportLab generated report card.
    * Click "Export Overall Excel", "Export Subject Excel", or "Export Absentees Excel" to download spreadsheets.
    * Verify that the candidate-facing results page still does not expose correct options.
14. Verify Phase 9 Production Hardening & Deployment:
    * Copy `.env.example` to `.env` in the backend folder and configure variables.
    * Run indexing migration: `python scripts/migrate_phase9_indexes.py`. Verify it runs safely and idempotently.
    * Run database backup: `python scripts/backup_database.py`. Verify it handles local/docker modes, checks commands, and prints error logs safely.
    * Run uploads backup: `python scripts/backup_uploads.py`. Verify it zips uploads directories.
    * Run docker compose validation: `docker compose -f docker-compose.prod.yml config`. Confirm syntax is valid.
    * Inspect [EXAM_DAY_CHECKLIST.md](file:///c:/Users/Gowtham/Desktop/phd-entrance-portal/docs/EXAM_DAY_CHECKLIST.md) and [DEPLOYMENT_READINESS_REPORT.md](file:///c:/Users/Gowtham/Desktop/phd-entrance-portal/docs/DEPLOYMENT_READINESS_REPORT.md).
15. Verify Phase 14 Force Reopen & Search UI:
    * Run the Phase 14 database migration script: `python scripts/migrate_phase14_force_reopen.py`.
    * Log in as Candidate, answer some questions, and click "Final Submit".
    * Log in as Admin, go to **Exam Control**, search the Candidate's Application ID or Number. Verify that input fields are large, and search is case-insensitive.
    * Perform "Force Reopen Submitted Attempt" by entering a reason and typing "REOPEN".
    * Confirm that attempt status returns to `IN_PROGRESS`.
    * Log back in as Candidate. Resume exam and verify that the timer resumes with remaining time, and previously selected answers are intact.

### Production Setup Instructions

1. **Copy Env Configuration**:
   * Copy `backend/.env.example` to `backend/.env` and fill real credentials.
   * Copy `frontend/.env.example` to `frontend/.env` and update API base URL.
   * **CAUTION**: Never commit `.env` files to git. Use strong secrets.

2. **Execute Database Index Optimizations**:
   ```bash
   cd backend
   python scripts/migrate_phase9_indexes.py
   ```

3. **Create Default Admin Account**:
   ```bash
   cd backend
   python scripts/create_default_admin.py
   ```
   *Note: Modify the default admin password inside `.env` immediately before exam day.*

4. **Launch Gunicorn & Production Nginx**:
   ```bash
   docker compose -f docker-compose.prod.yml up -d --build
   ```

5. **Locust Load Testing Instructions**:
   * Install locust: `pip install locust`
   * Run locust server: `locust -f load_tests/locustfile.py`
   * Open web interface: [http://localhost:8089](http://localhost:8089)
   * Configure users: 50 for smoke testing, 250 for production simulation, 300 for stress testing.

6. **Database & Uploads Backup**:
   * Database: `python scripts/backup_database.py` (checks commands, outputs timestamped sql dump)
   * Uploads: `python scripts/backup_uploads.py` (bundles excels & photographs to timestamped zip archive)

### Test URLs:
* **Candidate Login Screen**: [http://127.0.0.1:5173/](http://127.0.0.1:5173/)
* **Admin Login Screen**: [http://127.0.0.1:5173/admin](http://127.0.0.1:5173/admin) or [http://127.0.0.1:5173/admin/login](http://127.0.0.1:5173/admin/login)
* **Interactive OpenAPI Docs**: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
* **API Root**: [http://127.0.0.1:8000](http://127.0.0.1:8000)
* **Health Check**: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
