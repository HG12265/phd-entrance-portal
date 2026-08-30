# Exam-Day Readiness Checklist

Use this operational checklist to ensure smooth running of the PhD entrance examination on exam day.

---

## 1. Change Freeze Period

> [!IMPORTANT]
> The change freeze begins **24 hours** before the scheduled exam start time.

*   [ ] **No Code Changes**: Absolutely no code modifications, backend adjustments, or frontend releases are permitted after final QA approval.
*   [ ] **No Content Uploads**: No new question spreadsheet uploads or database schema modifications are allowed after final subject expert approvals.
*   [ ] **Database Snapshot**: Take a final database backup dump using the backup scripts and copy it to a secure secondary machine.
*   [ ] **Uploads Archive**: Zip and backup the uploads directory (excels, candidate photographs).
*   [ ] **Account Verification**: Verify that the main admin credentials work correctly.
*   [ ] **Dry Run Validation**: Conduct a 5-candidate mock dry-run simulation verifying start lock, questions rendering, timer sync, and final submits.

---

## 2. Before the Exam (T-minus 3 Hours)

*   [ ] **Server Metrics Audit**: Verify CPU, RAM, and Disk storage. Ensure at least 40% memory headroom is free.
*   [ ] **Check Connectivity**: Verify that the domain, SSL certificates, and network routings are fully operational.
*   [ ] **Database Verification**: Confirm MySQL is running, network ports are secure, and connections are responding.
*   [ ] **Static Photo Servings**: Check that candidate photographs serve cleanly from Nginx without latency.
*   [ ] **Question Bank Verification**: Verify that each academic department has exactly 70 active, shuffled questions ready in the database.
*   [ ] **Exam Session Parameters**: Double check session schedules, date/time boundaries, and durations in the admin dashboard.
*   [ ] **Emergency Protocols**: Ensure the IT support staff has recovery instructions, database restore notes, and contact directories.

---

## 3. During the Exam (Exam Session Active)

*   [ ] **Real-Time Monitoring**: Monitor server health statistics (`htop`, docker stats).
*   [ ] **Log Reviews**: Tail Gunicorn logs and `backend/logs/exam_events.log` for any database connection errors or save failures.
*   [ ] **Track Appeared Statistics**: Monitor active appeared counts, manual submits, and progress counters on the admin reports dashboard.
*   [ ] **Verify Auto-Submissions**: Ensure candidates whose time expires are auto-submitted by backend timeout finalization hooks.
*   [ ] **No Restarts**: Avoid restarting Nginx, backend Gunicorn workers, or MySQL services unless a critical deadlock occurs.

---

## 4. After the Exam (Session Completed)

*   [ ] **Enforce Submit Audits**: Verify that all attempts have status `submitted` or `auto_submitted`. Ensure zero attempts remain in `in_progress` status.
*   [ ] **Final Backups**: Execute a final post-exam database backup dump and store copies on two separate external drives.
*   [ ] **Performance Export**: Download the overall leaderboard and subject-wise leaderboards in Excel format.
*   [ ] **Absentee List**: Download the final absentees report spreadsheet.
*   [ ] **Candidate PDF Archive**: Generate and export the evaluation PDF cards for all candidates. Store them in a secure drive.
*   [ ] **Lock Access**: Deactivate candidate login routes if necessary by toggling active session switches or database flags.
