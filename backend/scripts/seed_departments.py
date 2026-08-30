import os
import sys

# Ensure parent directory (backend/) is in the python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.database import SessionLocal
from app.models.department import Department

# The final official list of 31 departments
FINAL_DEPARTMENTS = [
    {"name": "Biochemistry", "code": "BC"},
    {"name": "Biotechnology", "code": "BT"},
    {"name": "Botany", "code": "BOT"},
    {"name": "Chemistry", "code": "CHEM"},
    {"name": "Commerce", "code": "COM"},
    {"name": "Computer Science", "code": "CS"},
    {"name": "Economics", "code": "ECO"},
    {"name": "Education", "code": "EDU"},
    {"name": "English", "code": "ENG"},
    {"name": "Environmental Science", "code": "ES"},
    {"name": "Food Science Technology and Nutrition", "code": "FSN"},
    {"name": "Geology", "code": "GL"},
    {"name": "History", "code": "HIS"},
    {"name": "Journalism and Mass Communication", "code": "JMC"},
    {"name": "Library and Information Science", "code": "LIS"},
    {"name": "Management", "code": "MS"},
    {"name": "Mathematics", "code": "MATH"},
    {"name": "Microbiology", "code": "MB"},
    {"name": "Nutrition and Dietetics", "code": "ND"},
    {"name": "Physics", "code": "PHY"},
    {"name": "Political Science", "code": "POL"},
    {"name": "Psychology", "code": "PSY"},
    {"name": "Sericulture", "code": "SERI"},
    {"name": "Sociology", "code": "SOC"},
    {"name": "Statistics", "code": "STAT"},
    {"name": "Tamil", "code": "TAM"},
    {"name": "Textiles and Apparel Design", "code": "TAD"},
    {"name": "Zoology", "code": "ZOO"},
    {"name": "Energy Science", "code": "ENS"},
    {"name": "Energy Technology", "code": "ENT"},
    {"name": "Physics Interdisciplinary with Energy Science", "code": "PIES"}
]

# Rename mapping to preserve candidate and question references
RENAME_MAP = {
    "Food Science and Nutrition": "Food Science Technology and Nutrition",
    "Management Studies": "Management"
}

def seed():
    db = SessionLocal()
    try:
        # 1. Handle renames first
        for old_name, new_name in RENAME_MAP.items():
            existing = db.query(Department).filter(Department.department_name == old_name).first()
            if existing:
                print(f"Renaming department: '{old_name}' -> '{new_name}'")
                existing.department_name = new_name
                db.commit()
                
        # 2. Deactivate any department that is not in the final list
        final_names = {d["name"] for d in FINAL_DEPARTMENTS}
        all_depts = db.query(Department).all()
        for dept in all_depts:
            if dept.department_name not in final_names:
                if dept.is_active:
                    print(f"Deactivating department: {dept.department_name} ({dept.department_code})")
                    dept.is_active = False
            else:
                if not dept.is_active:
                    print(f"Activating department: {dept.department_name} ({dept.department_code})")
                    dept.is_active = True
        db.commit()
        
        # 3. Add or update departments from the final list
        added_count = 0
        updated_count = 0
        for item in FINAL_DEPARTMENTS:
            existing = db.query(Department).filter(
                (Department.department_name == item["name"]) |
                (Department.department_code == item["code"])
            ).first()
            
            if not existing:
                new_dept = Department(
                    department_name=item["name"],
                    department_code=item["code"],
                    description=f"{item['name']} Department",
                    is_active=True
                )
                db.add(new_dept)
                added_count += 1
                print(f"Adding new department: {item['name']} ({item['code']})")
            else:
                # Update name or code if mismatch
                if existing.department_name != item["name"] or existing.department_code != item["code"]:
                    print(f"Updating department mapping: '{existing.department_name}' ({existing.department_code}) -> '{item['name']}' ({item['code']})")
                    existing.department_name = item["name"]
                    existing.department_code = item["code"]
                    updated_count += 1
                existing.is_active = True
                
        db.commit()
        print(f"Sync complete. Added: {added_count}, Updated: {updated_count}.")
    except Exception as e:
        db.rollback()
        print(f"Failed to sync departments: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    seed()
