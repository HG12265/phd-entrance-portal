from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.settings import SystemSetting
from app.models.admin import AdminUser
from app.utils.auth_dependency import get_current_admin
from pydantic import BaseModel

router = APIRouter()

class SettingUpdatePayload(BaseModel):
    value: str

@router.get("/public/{key}")
def get_public_setting(key: str, db: Session = Depends(get_db)):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        if key == "portal_title":
            return {"key": "portal_title", "value": "PhD Admission Entrance"}
        raise HTTPException(status_code=404, detail="Setting not found")
    return {"key": setting.key, "value": setting.value}

@router.get("/admin/all")
def get_all_settings(db: Session = Depends(get_db), current_admin: AdminUser = Depends(get_current_admin)):
    settings = db.query(SystemSetting).all()
    # Ensure default portal_title is returned if not in DB
    if not any(s.key == "portal_title" for s in settings):
        return [{"key": "portal_title", "value": "PhD Admission Entrance"}]
    return settings

@router.put("/admin/{key}")
def update_setting(key: str, payload: SettingUpdatePayload, db: Session = Depends(get_db), current_admin: AdminUser = Depends(get_current_admin)):
    setting = db.query(SystemSetting).filter(SystemSetting.key == key).first()
    if not setting:
        setting = SystemSetting(key=key, value=payload.value)
        db.add(setting)
    else:
        setting.value = payload.value
    db.commit()
    return {"key": key, "value": setting.value}
