# Database Restoration Guide

Follow these instructions to restore a database backup in case of emergency on exam day.

---

## 1. Restoration using Local MySQL Host

If running the application locally outside Docker, use standard mysql client utilities:

```bash
# 1. Create target database if it does not exist (optional)
mysql -h 127.0.0.1 -P 3307 -u root -p -e "CREATE DATABASE IF NOT EXISTS phd_entrance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 2. Restore the SQL backup dump
mysql -h 127.0.0.1 -P 3307 -u root -p phd_entrance_db < backups/database/phd_entrance_db_YYYYMMDD_HHMMSS.sql
```

---

## 2. Restoration using Docker Compose MySQL Container

If deploying via the production `docker-compose.prod.yml` configuration:

```bash
# 1. Copy the sql dump into the mysql container
docker cp backups/database/phd_entrance_db_YYYYMMDD_HHMMSS.sql phd_mysql:/tmp/backup.sql

# 2. Re-create database safely inside the container (optional)
docker exec -it phd_mysql mysql -uroot -proot -e "CREATE DATABASE IF NOT EXISTS phd_entrance_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 3. Restore the SQL dump inside container
docker exec -it phd_mysql sh -c 'mysql -uroot -proot phd_entrance_db < /tmp/backup.sql'

# 4. Clean up temp files
docker exec -it phd_mysql rm /tmp/backup.sql
```

---

## 3. Uploads Folder Restoration

To restore candidate photographs or excels archives:

```bash
# Extract the zip file contents back to backend/uploads directory
# For example, on Windows using PowerShell:
Expand-Archive -Path backups/uploads/uploads_backup_YYYYMMDD_HHMMSS.zip -DestinationPath backend/uploads -Force
```
