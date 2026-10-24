import secrets
from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..anomaly_detector import AnomalyDetector
from ..database import get_db
from ..face_engine import FaceEngine
from ..models import AnomalyType, Attendance, Employee
from ..schemas import FaceAttendancePayload, SelfRegistration

router = APIRouter(prefix="/api/public", tags=["employee self-service"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def self_register(payload: SelfRegistration, db: Session = Depends(get_db)) -> dict[str, str]:
    email = str(payload.email).lower()
    if db.query(Employee).filter(Employee.email == email).first():
        raise HTTPException(status_code=409, detail="An account already exists for this email")

    image = FaceEngine.decode_image_from_base64(payload.image_base64)
    embedding = FaceEngine.extract_embedding(image)
    employee_code = f"ATT-{secrets.token_hex(6).upper()}"
    while db.query(Employee.id).filter(Employee.employee_code == employee_code).first():
        employee_code = f"ATT-{secrets.token_hex(6).upper()}"

    employee = Employee(
        employee_code=employee_code,
        full_name=payload.full_name.strip(),
        email=email,
        department=payload.department.strip(),
        biometric_consent=True,
        consent_timestamp=datetime.now(),
        face_embedding=FaceEngine.encrypt_embedding(embedding),
    )
    db.add(employee)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account already exists for this email")
    return {
        "employee_code": employee_code,
        "message": "Registration and encrypted face enrollment complete. Keep your employee code private.",
    }


def _verify_employee_face(
    payload: FaceAttendancePayload, db: Session
) -> tuple[Employee, datetime]:
    employee = (
        db.query(Employee)
        .filter(Employee.employee_code == payload.employee_code, Employee.is_active.is_(True))
        .first()
    )
    if employee is None:
        raise HTTPException(status_code=404, detail="Active employee not found")
    if not employee.biometric_consent or not employee.face_embedding:
        raise HTTPException(status_code=403, detail="Face enrollment is not available for this employee")

    image = FaceEngine.decode_image_from_base64(payload.image_base64)
    input_embedding = FaceEngine.extract_embedding(image)
    stored_embedding = FaceEngine.decrypt_embedding(employee.face_embedding)
    matched, _confidence = FaceEngine.match_face(input_embedding, stored_embedding)
    if not matched:
        raise HTTPException(status_code=401, detail="Face verification failed")
    return employee, datetime.now()


@router.post("/attendance/check-in", status_code=status.HTTP_201_CREATED)
def self_check_in(payload: FaceAttendancePayload, db: Session = Depends(get_db)) -> dict[str, object]:
    employee, now = _verify_employee_face(payload, db)
    today_entry = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee.id, Attendance.date == date.today())
        .order_by(Attendance.check_in.desc())
        .first()
    )
    if today_entry:
        raise HTTPException(status_code=409, detail="Attendance is already recorded for today")

    has_anomaly, anomaly_type, notes = AnomalyDetector.evaluate_checkin(db, employee.id, now)
    attendance = Attendance(
        employee_id=employee.id,
        date=now.date(),
        check_in=now,
        status=AnomalyDetector.determine_punctuality(now),
        verified_via_face=True,
        anomaly_flag=has_anomaly,
        anomaly_reason=anomaly_type,
        anomaly_notes=notes,
    )
    db.add(attendance)
    db.commit()
    return {
        "employee": employee.full_name,
        "employee_code": employee.employee_code,
        "time": now.isoformat(timespec="seconds"),
        "status": attendance.status.value,
        "anomaly_flag": has_anomaly,
        "anomaly_reason": anomaly_type.value,
    }


@router.post("/attendance/check-out")
def self_check_out(payload: FaceAttendancePayload, db: Session = Depends(get_db)) -> dict[str, str]:
    employee, now = _verify_employee_face(payload, db)
    attendance = (
        db.query(Attendance)
        .filter(Attendance.employee_id == employee.id, Attendance.date == date.today())
        .order_by(Attendance.check_in.desc())
        .first()
    )
    if attendance is None:
        raise HTTPException(status_code=404, detail="Check in before recording check-out")
    if attendance.check_out is not None:
        raise HTTPException(status_code=409, detail="Check-out is already recorded")
    if now < attendance.check_in:
        now = attendance.check_in
    attendance.check_out = now
    db.commit()
    return {"employee": employee.full_name, "time": now.isoformat(timespec="seconds")}
