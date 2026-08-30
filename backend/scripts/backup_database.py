import os
import sys
import subprocess
from datetime import datetime

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

def check_command_exists(cmd):
    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, shell=True)
        return True
    except Exception:
        return False

def run_backup():
    print("Starting database backup process...")
    
    # Load backup configuration env variables
    backup_mode = os.getenv("BACKUP_MODE", "local").lower()
    container_name = os.getenv("MYSQL_CONTAINER_NAME", "phd_mysql")
    
    # Set up backup directory relative to backend folder
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(backend_dir, "backups", "database")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"phd_entrance_db_{timestamp}.sql"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    # Check dependencies and configure execute command
    if backup_mode == "docker":
        # Docker Mode: Execute mysqldump inside container
        print(f"Backup Mode: Docker container ({container_name})")
        if not check_command_exists("docker --version"):
            print("Error: 'docker' command is not available in the system environment.")
            return False
            
        # Avoid printing password to logs
        cmd = f'docker exec {container_name} mysqldump -u{DB_USER} -p{DB_PASSWORD} {DB_NAME} > "{backup_path}"'
    else:
        # Local Mode: Use local mysqldump command
        print("Backup Mode: Local host")
        if not check_command_exists("mysqldump --version"):
            print("Error: 'mysqldump' utility is not installed or not in PATH.")
            print("To run local backup, please install MySQL Client Utilities or set BACKUP_MODE=docker.")
            return False
            
        cmd = f'mysqldump -h{DB_HOST} -P{DB_PORT} -u{DB_USER} -p{DB_PASSWORD} {DB_NAME} > "{backup_path}"'

    try:
        # Run command securely (suppressing traceback from exposing password)
        print("Running backup command...")
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        if result.returncode == 0:
            print(f"Database backup COMPLETED successfully!")
            print(f"Backup File: {backup_path}")
            return True
        else:
            print("Database backup FAILED!")
            # Strip DB password from error output to be secure
            err_msg = result.stderr.replace(DB_PASSWORD, "*****")
            print(f"Error Details: {err_msg}")
            return False
    except Exception as e:
        print(f"An unexpected exception occurred during backup: {str(e)}")
        return False

if __name__ == "__main__":
    run_backup()
