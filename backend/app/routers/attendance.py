from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from ..anomaly_detector import AnomalyDetector
from ..auth import require_admin
from ..database import get_db
from ..face_engine import FaceEngine
from ..models import AnomalyType, Attendance, Employee
from ..schemas import AttendanceUpdate, CheckoutPayload, VerifyAttendancePayload

router = APIRouter(prefix="/api/attendance", tags=["attendance"], dependencies=[Depends(require_admin)])


@router.post("/mark", status_code=status.HTTP_201_CREATED)
def mark_attendance(payload: VerifyAttendancePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    employee = db.query(Employee).filter(Employee.employee_code == payload.employee_code).first()
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=404, detail="Active employee not found")

    now = datetime.now()
    existing = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee.id, Attendance.date == date.today())
        .first()
    )
    recent_reentry = (
        db.query(Attendance)
        .filter(
            Attendance.employee_id == employee.id,
            Attendance.check_in >= now - timedelta(minutes=10),
            Attendance.check_in <= now,
        )
        .first()
    )
    if existing and recent_reentry is None:
        raise HTTPException(status_code=409, detail="Attendance has already been recorded for today")

    verified_via_face = False
    if employee.biometric_consent and employee.face_embedding and not payload.manual_override:
        if not payload.image_base64:
            raise HTTPException(status_code=400, detail="Face verification image is required")
        image = FaceEngine.decode_image_from_base64(payload.image_base64)
        input_embedding = FaceEngine.extract_embedding(image)
        stored_embedding = FaceEngine.decrypt_embedding(employee.face_embedding)
        matched, _confidence = FaceEngine.match_face(input_embedding, stored_embedding)
        if not matched:
            raise HTTPException(status_code=401, detail="Face verification failed")
        verified_via_face = True

    has_anomaly, anomaly_type, anomaly_notes = AnomalyDetector.evaluate_checkin(db, employee.id, now)
    attendance = Attendance(
        employee_id=employee.id,
        date=now.date(),
        check_in=now,
        status=AnomalyDetector.determine_punctuality(now),
        verified_via_face=verified_via_face,
        anomaly_flag=has_anomaly,
        anomaly_reason=anomaly_type,
        anomaly_notes=anomaly_notes,
    )
    db.add(attendance)
    db.commit()
    db.refresh(attendance)
    return {
        "status": "success",
        "employee": employee.full_name,
        "time": now.isoformat(timespec="seconds"),
        "punctuality": attendance.status.value,
        "verified_via_face": verified_via_face,
        "anomaly_flag": has_anomaly,
        "anomaly_reason": anomaly_type.value,
        "anomaly_notes": anomaly_notes,
    }


@router.post("/checkout")
def check_out(payload: CheckoutPayload, db: Session = Depends(get_db)) -> dict[str, str]:
    employee = db.query(Employee).filter(Employee.employee_code == payload.employee_code).first()
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=404, detail="Active employee not found")
    attendance = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee.id, Attendance.date == date.today())
        .order_by(Attendance.check_in.desc())
        .first()
    )
    if attendance is None:
        raise HTTPException(status_code=404, detail="No attendance entry exists for today")
    if attendance.check_out is not None:
        raise HTTPException(status_code=409, detail="Check-out has already been recorded")
    attendance.check_out = datetime.now()
    db.commit()
    return {"status": "success", "time": attendance.check_out.isoformat(timespec="seconds")}


@router.patch("/{record_id}")
def update_attendance(
    record_id: int, payload: AttendanceUpdate, db: Session = Depends(get_db)
) -> dict[str, object]:
    record = db.query(Attendance).filter(Attendance.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(record, field, value)
    if "check_in" in updates:
        record.date = record.check_in.date()
    if record.check_out and record.check_out < record.check_in:
        raise HTTPException(status_code=422, detail="Check-out must not be earlier than check-in")
    if record.anomaly_flag is False:
        record.anomaly_reason = AnomalyType.NONE
    elif record.anomaly_flag and record.anomaly_reason is AnomalyType.NONE:
        record.anomaly_reason = AnomalyType.GEO_MISMATCH
    db.commit()
    return {"message": "Attendance record updated", "id": record.id}


@router.delete("/{record_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(record_id: int, db: Session = Depends(get_db)) -> Response:
    record = db.query(Attendance).filter(Attendance.id == record_id).first()
    if record is None:
        raise HTTPException(status_code=404, detail="Attendance record not found")
    db.delete(record)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
