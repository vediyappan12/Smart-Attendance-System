import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import Attendance, Employee
from ..schemas import AttendanceReportResponse

router = APIRouter(prefix="/api/reports", tags=["reports"], dependencies=[Depends(require_admin)])


def _records_query(
    db: Session, start_date: date | None, end_date: date | None, anomalies_only: bool
):
    if start_date and end_date and start_date > end_date:
        raise HTTPException(status_code=422, detail="start_date must not be after end_date")
    query = db.query(Attendance, Employee).join(Employee, Attendance.employee_id == Employee.id)
    if start_date:
        query = query.filter(Attendance.date >= start_date)
    if end_date:
        query = query.filter(Attendance.date <= end_date)
    if anomalies_only:
        query = query.filter(Attendance.anomaly_flag.is_(True))
    return query.order_by(Attendance.check_in.desc())


@router.get("", response_model=list[AttendanceReportResponse])
def get_reports(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    anomalies_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> list[AttendanceReportResponse]:
    rows = _records_query(db, start_date, end_date, anomalies_only).all()
    return [
        AttendanceReportResponse(
            id=attendance.id,
            date=attendance.date,
            employee_code=employee.employee_code,
            full_name=employee.full_name,
            department=employee.department,
            check_in=attendance.check_in,
            check_out=attendance.check_out,
            status=attendance.status,
            verified_via_face=attendance.verified_via_face,
            anomaly_flag=attendance.anomaly_flag,
            anomaly_reason=attendance.anomaly_reason,
            anomaly_notes=attendance.anomaly_notes,
        )
        for attendance, employee in rows
    ]


@router.get("/summary")
def get_summary(db: Session = Depends(get_db)) -> dict[str, int]:
    today = date.today()
    records = db.query(Attendance).filter(Attendance.date == today).all()
    return {
        "employees": db.query(Employee).filter(Employee.is_active.is_(True)).count(),
        "present_today": (
            db.query(func.count(func.distinct(Attendance.employee_id)))
            .filter(Attendance.date == today)
            .scalar()
            or 0
        ),
        "late_today": sum(record.status.value == "LATE" for record in records),
        "anomalies_today": sum(record.anomaly_flag for record in records),
    }


@router.get("/export.csv")
def export_reports(
    start_date: date | None = Query(None),
    end_date: date | None = Query(None),
    anomalies_only: bool = Query(False),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    rows = _records_query(db, start_date, end_date, anomalies_only).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["date", "employee_code", "full_name", "department", "check_in", "check_out", "status", "face_verified", "anomaly", "anomaly_reason", "notes"]
    )
    for attendance, employee in rows:
        writer.writerow(
            [
                attendance.date,
                employee.employee_code,
                employee.full_name,
                employee.department,
                attendance.check_in.isoformat(),
                attendance.check_out.isoformat() if attendance.check_out else "",
                attendance.status.value,
                attendance.verified_via_face,
                attendance.anomaly_flag,
                attendance.anomaly_reason.value,
                attendance.anomaly_notes or "",
            ]
        )
    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="attendance-{date.today().isoformat()}.csv"'},
    )
