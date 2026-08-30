import os
import sys
import zipfile
from datetime import datetime

def run_backup_uploads():
    print("Starting uploads backup process...")
    
    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    backup_dir = os.path.join(backend_dir, "backups", "uploads")
    os.makedirs(backup_dir, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"uploads_backup_{timestamp}.zip"
    backup_path = os.path.join(backup_dir, backup_filename)
    
    uploads_root = os.path.join(backend_dir, "uploads")
    if not os.path.exists(uploads_root):
        print(f"Error: Uploads directory '{uploads_root}' does not exist.")
        return False
        
    folders_to_backup = ["candidate_photos", "candidate_excels", "question_excels"]
    
    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for folder in folders_to_backup:
                folder_path = os.path.join(uploads_root, folder)
                if not os.path.exists(folder_path):
                    print(f"Warning: Subfolder '{folder}' does not exist. Skipping.")
                    continue
                    
                print(f"Archiving folder: {folder}...")
                for root, dirs, files in os.walk(folder_path):
                    for file in files:
                        file_abs_path = os.path.join(root, file)
                        # Store file using relative path inside zip
                        file_rel_path = os.path.relpath(file_abs_path, uploads_root)
                        zipf.write(file_abs_path, file_rel_path)
                        
        print("Uploads backup COMPLETED successfully!")
        print(f"Backup Archive: {backup_path}")
        return True
    except Exception as e:
        print(f"Uploads backup FAILED! Error Details: {str(e)}")
        return False

if __name__ == "__main__":
    run_backup_uploads()
