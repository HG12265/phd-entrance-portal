from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from io import BytesIO
from typing import Optional

from app.database import get_db
from app.models.admin import AdminUser
from app.models.candidate import Candidate
from app.utils.auth_dependency import get_current_admin
from app.services import report_service
from app.logging_config import log_info

router = APIRouter(prefix="/api/admin/reports")

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 15 ROUTES — defined first (static before dynamic)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/overall-result")
def get_overall_result_route(
    exam_session_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Returns overall summary + paginated candidate result table (Phase 15)."""
    return report_service.get_overall_result(db, exam_session_id, department_id, result_status, search, page, limit)

@router.get("/department-wise")
def get_department_wise_route(
    exam_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Returns department-wise report table (Phase 15)."""
    return report_service.get_department_wise_report(db, exam_session_id)

@router.get("/export/department-wise-excel")
def export_department_wise_excel_route(
    exam_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generates department-wise summary Excel (Phase 15)."""
    log_info(f"Admin exported department-wise summary Excel: admin_email={admin.email}")
    excel_bytes = report_service.export_department_wise_excel(db, exam_session_id)
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=department_wise_summary.xlsx"}
    )

@router.get("/export/department-wise-details-excel")
def export_department_wise_details_excel_route(
    exam_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generates department-wise details Excel workbook with a sheet per department (Phase 18)."""
    log_info(f"Admin exported department-wise details Excel: admin_email={admin.email}")
    excel_bytes = report_service.export_department_wise_details_excel(db, exam_session_id)
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=department_wise_details.xlsx"}
    )


@router.get("/export/department-report-excel/{department_id}")
def export_department_report_excel_route(
    department_id: int,
    exam_session_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generates selected department result Excel (Phase 15)."""
    log_info(f"Admin exported department report Excel: dept_id={department_id}, admin_email={admin.email}")
    excel_bytes = report_service.export_department_report_excel(db, department_id, exam_session_id, result_status)
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=department_{department_id}_result.xlsx"}
    )

@router.get("/export/overall-result-excel")
def export_overall_result_excel_route(
    exam_session_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generates overall result Excel with Phase 12 fields (Phase 15)."""
    log_info(f"Admin exported overall result Excel: admin_email={admin.email}")
    excel_bytes = report_service.export_overall_result_excel(db, exam_session_id, department_id, result_status)
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=overall_result.xlsx"}
    )


@router.get("/export/overall-result-pdf")
def export_overall_result_pdf_route(
    exam_session_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generates overall result PDF with requested fields (Phase 15)."""
    log_info(f"Admin exported overall result PDF: admin_email={admin.email}")
    pdf_bytes = report_service.export_overall_result_pdf(db, exam_session_id, department_id, result_status)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=overall_result.pdf"}
    )


@router.get("/export/department-wise-pdf")
def export_department_wise_pdf_route(
    exam_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generates department-wise summary PDF (Phase 15)."""
    log_info(f"Admin exported department-wise summary PDF: admin_email={admin.email}")
    pdf_bytes = report_service.export_department_wise_pdf(db, exam_session_id)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=department_wise_summary.pdf"}
    )


@router.get("/export/department-report-pdf/{department_id}")
def export_department_report_pdf_route(
    department_id: int,
    exam_session_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Generates selected department result PDF (Phase 15)."""
    log_info(f"Admin exported department report PDF: dept_id={department_id}, admin_email={admin.email}")
    pdf_bytes = report_service.export_department_report_pdf(db, department_id, exam_session_id, result_status)
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=department_{department_id}_result.pdf"}
    )


# Dynamic route LAST to avoid shadowing static routes
@router.get("/department/{department_id}")
def get_department_detail_route(
    department_id: int,
    exam_session_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """Returns full department detail — summary, results, absentees (Phase 15)."""
    return report_service.get_department_detail(db, department_id, exam_session_id, result_status, search)


@router.get("/summary")
def get_reports_summary(
    exam_session_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Returns high-level statistics summary of active candidates, appeared, passed, failed counts.
    """
    return report_service.get_report_summary(db, exam_session_id, department_id)

@router.get("/subject-summary")
def get_reports_subject_summary(
    exam_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Returns statistics summaries grouped by academic department subjects.
    """
    return report_service.get_subject_summary(db, exam_session_id)

@router.get("/leaderboard/subject/{department_id}")
def get_subject_leaderboard_route(
    department_id: int,
    exam_session_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Returns subject-wise leaderboard list.
    """
    return report_service.get_subject_leaderboard(
        db, department_id, exam_session_id, result_status, search, page, limit
    )

@router.get("/leaderboard/overall")
def get_overall_leaderboard_route(
    department_id: Optional[int] = Query(None),
    exam_session_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Returns overall candidate leaderboard list.
    """
    return report_service.get_overall_leaderboard(
        db, department_id, exam_session_id, result_status, search, page, limit
    )

@router.get("/absentees")
def get_absentees_route(
    exam_session_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Returns list of active candidates who did not submit exam attempts.
    """
    return report_service.get_absentees(db, exam_session_id, department_id, search, page, limit)

@router.get("/candidate/{candidate_id}")
def get_candidate_individual_report(
    candidate_id: int,
    exam_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Returns question-by-question candidate evaluations including options, answers (restricted to admin).
    """
    return report_service.get_candidate_report(db, candidate_id, exam_session_id)

@router.get("/attempt/{attempt_id}")
def get_attempt_individual_report(
    attempt_id: int,
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Returns question-by-question candidate attempt evaluations.
    """
    return report_service.get_attempt_report(db, attempt_id)

# ----------------- EXPORT ENDPOINTS -----------------

@router.get("/export/overall-excel")
def export_overall_excel_route(
    department_id: Optional[int] = Query(None),
    exam_session_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Generates and returns overall leaderboard Excel spreadsheet.
    """
    log_info(f"Admin exported overall leaderboard Excel: admin_email={admin.email}")
    excel_bytes = report_service.export_leaderboard_excel(db, department_id, exam_session_id, result_status)
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=overall_leaderboard.xlsx"}
    )

@router.get("/export/subject-excel/{department_id}")
def export_subject_excel_route(
    department_id: int,
    exam_session_id: Optional[int] = Query(None),
    result_status: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Generates and returns subject-wise leaderboard Excel spreadsheet.
    """
    log_info(f"Admin exported subject leaderboard Excel: dept_id={department_id}, admin_email={admin.email}")
    excel_bytes = report_service.export_leaderboard_excel(db, department_id, exam_session_id, result_status)
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=subject_{department_id}_leaderboard.xlsx"}
    )

@router.get("/export/absentees-excel")
def export_absentees_excel_route(
    exam_session_id: Optional[int] = Query(None),
    department_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Generates and returns absentees Excel spreadsheet.
    """
    log_info(f"Admin exported absentees Excel: admin_email={admin.email}")
    excel_bytes = report_service.export_absentees_excel(db, department_id, exam_session_id)
    return StreamingResponse(
        BytesIO(excel_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=absentees_list.xlsx"}
    )

@router.get("/export/candidate-pdf/{candidate_id}")
def export_candidate_pdf_route(
    candidate_id: int,
    exam_session_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    admin: AdminUser = Depends(get_current_admin)
):
    """
    Generates and returns candidate score card PDF file report.
    """
    # Fetch candidate safe application number for filename formatting
    candidate = db.query(Candidate).filter(Candidate.id == candidate_id).first()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found.")
        
    app_num_safe = candidate.application_number.replace("/", "-")
    log_info(f"Admin exported candidate report PDF: candidate_id={candidate_id}, app_num={candidate.application_number}, admin_email={admin.email}")
    pdf_bytes = report_service.export_candidate_pdf(db, candidate_id, exam_session_id)
    
    return StreamingResponse(
        BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=candidate_report_{app_num_safe}.pdf"}
    )
