# PhD Entrance Exam Portal - Phase 3 Testing Report

## Test Environment

* **Backend URL**: http://127.0.0.1:8000
* **Frontend URL**: http://127.0.0.1:5173
* **Database**: MySQL (v8.0) running on Docker container port 3307
* **Date and Time of Testing**: 2026-07-03T20:36:00+05:30

## Summary

* **Total Tests**: 18
* **Passed**: 18
* **Failed**: 0
* **Fixed**: 0
* **Pending**: 0

---

## Detailed Test Results

| No | Test Case | Status | Result / Observation | Fix Applied |
| :--- | :--- | :---: | :--- | :--- |
| 1 | Backend Startup Test | ✅ Passed | Root endpoint (`/`), Health check (`/health`), and Swagger (`/docs`) run successfully. | None required |
| 2 | Frontend Startup Test | ✅ Passed | React Vite dev server starts successfully. Admin login screen displays correctly. | None required |
| 3 | Admin Login Test | ✅ Passed | Login retrieves access token, sets `admin_token` and `admin_user` in `localStorage`, and redirects to Dashboard. | None required |
| 4 | Unauthorized API Test | ✅ Passed | Calls to `/api/admin/candidates`, `/api/admin/departments`, and `/api/admin/candidates/upload-excel` without token return 401. | None required |
| 5 | Candidate Excel Upload - Valid Data Test | ✅ Passed | Ingestion of 3 candidates succeeds. `success_count` is 3, `failed_count` is 0. Candidates stored. | None required |
| 6 | Duplicate Application Number Inside Excel Test | ✅ Passed | First row imported, duplicate is skipped. `duplicate_in_excel_count` increments to 1. Error message recorded. | None required |
| 7 | Duplicate Application Number Already in DB Test | ✅ Passed | Ingesting duplicate application numbers skips insertion. `duplicate_in_database_count` increments to 1. | None required |
| 8 | Invalid DOB Format Test | ✅ Passed | Row skipped safely without crashing the backend. Error report details DOB mismatch. | None required |
| 9 | Applied Subject Department Mapping Test | ✅ Passed | Maps successfully using either department name or department code. Non-existing subjects fail. | None required |
| 10 | Missing Photo Test | ✅ Passed | Candidate is saved with `photo_status` set to "missing", and `photo_path` is null. UI displays red placeholder. | None required |
| 11 | Photo Upload and Remap Test | ✅ Passed | POST `/api/admin/candidates/upload-photos` successfully matches CET/PHD/J26/1001 with CET-PHD-J26-1001.JPG. | None required |
| 12 | Manual Photo Folder Remap Test | ✅ Passed | Manually placing image files and running rescanner matches candidate and updates `photo_status` to "available". | None required |
| 13 | Candidate List Search Test | ✅ Passed | Case-insensitive matching filters exact candidates by name, app no, email, or mobile. | None required |
| 14 | Candidate List Filter Test | ✅ Passed | Department filtering and Photo Status filtering return exact subsets while preserving paging structures. | None required |
| 15 | Candidate Details Page Test | ✅ Passed | Detail view lists candidate details, subject name, mapped department, and photo image/placeholder. | None required |
| 16 | Import Logs Test | ✅ Passed | Spreadsheet imports generate matching row audit database lines in the `import_logs` table. | None required |
| 17 | Regression Test for Phase 2 | ✅ Passed | JWT validation, department CRUD, soft deletion, and logout functions remain fully functional. | None required |
| 18 | Dashboard Count Test | ✅ Passed | Real-time counts for Departments, Candidates, and Missing Photos render on dashboard without crashing. | None required |

---

## Bugs Found and Fixed

No bugs were found in the current implementation. All automated validation checks and regression assertions passed successfully.

---

## API Verification

| Method | Endpoint | Expected Status | Actual Status | Result |
| :--- | :--- | :---: | :---: | :---: |
| `POST` | `/api/admin/auth/login` | 200 | 200 | ✅ Passed |
| `GET` | `/api/admin/candidates` | 200 | 200 | ✅ Passed |
| `GET` | `/api/admin/candidates/{id}` | 200 | 200 | ✅ Passed |
| `POST` | `/api/admin/candidates/upload-excel` | 200 | 200 | ✅ Passed |
| `POST` | `/api/admin/candidates/upload-photos` | 200 | 200 | ✅ Passed |
| `POST` | `/api/admin/candidates/remap-photos` | 200 | 200 | ✅ Passed |
| `GET` | `/api/admin/departments` | 200 | 200 | ✅ Passed |

---

## Frontend Verification

| Page URL | Expected Behavior | Actual Behavior | Result |
| :--- | :--- | :--- | :---: |
| `http://127.0.0.1:5173/admin/login` | Displays login form and stores token on submit. | Renders form, accepts valid credentials, redirects. | ✅ Passed |
| `http://127.0.0.1:5173/admin/dashboard` | Displays real-time candidate, missing photo, and department stats. | Displays dynamic grid with live statistics and recent candidates. | ✅ Passed |
| `http://127.0.0.1:5173/admin/candidates` | Renders candidate registry list with search, filter, and pagination. | Displays registry table with search bars and filters. | ✅ Passed |
| `http://127.0.0.1:5173/admin/candidates/upload` | Upload panel for candidate Excel spreadsheets and photo folders. | Form uploads data and renders processing summaries. | ✅ Passed |
| `http://127.0.0.1:5173/admin/candidates/{id}` | Displays detail panel with student photograph or placeholder card. | Displays fields and student photo accurately. | ✅ Passed |

---

## Database Verification

* **`candidates` table records**: Properly holds all parsed columns (`application_number`, `dob`, `mobile_number`, `applied_subject`, `photo_filename`, `photo_path`, `photo_status`, `import_batch_id`, `is_active`, `created_at`, `updated_at`).
* **`import_logs` table records**: Holds file metadata (`file_name`, `total_records`, `success_count`, `failed_count`, `error_details`).
* **`photo_status` updates**: Correctly toggles between `available` and `missing` based on image matches.
* **department mapping**: Successfully maps `Applied Subject` using department name or code and sets foreign key constraints.

---

## Final Decision

**Phase 3 is fully verified and ready for Phase 4.**
