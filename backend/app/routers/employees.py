from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..face_engine import FaceEngine
from ..models import Employee
from ..schemas import EmployeeCreate, EmployeeResponse, RegisterFacePayload

router = APIRouter(prefix="/api/employees", tags=["employees"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[EmployeeResponse])
def list_employees(db: Session = Depends(get_db)) -> list[Employee]:
    return db.query(Employee).order_by(Employee.full_name).all()


@router.post("", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
def register_employee(payload: EmployeeCreate, db: Session = Depends(get_db)) -> Employee:
    existing = (
        db.query(Employee)
        .filter(or_(Employee.employee_code == payload.employee_code, Employee.email == str(payload.email)))
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail="Employee code or email already exists")

    employee = Employee(
        employee_code=payload.employee_code,
        full_name=payload.full_name.strip(),
        email=str(payload.email),
        department=payload.department.strip(),
        biometric_consent=payload.biometric_consent,
        consent_timestamp=datetime.now() if payload.biometric_consent else None,
    )
    db.add(employee)
    db.commit()
    db.refresh(employee)
    return employee


@router.post("/biometrics/enroll", status_code=status.HTTP_201_CREATED)
def enroll_biometric(payload: RegisterFacePayload, db: Session = Depends(get_db)) -> dict[str, str]:
    employee = db.query(Employee).filter(Employee.employee_code == payload.employee_code).first()
    if employee is None or not employee.is_active:
        raise HTTPException(status_code=404, detail="Active employee not found")
    if not employee.biometric_consent:
        raise HTTPException(status_code=403, detail="Employee has not granted biometric consent")

    image = FaceEngine.decode_image_from_base64(payload.image_base64)
    embedding = FaceEngine.extract_embedding(image)
    employee.face_embedding = FaceEngine.encrypt_embedding(embedding)
    db.commit()
    return {"message": "Encrypted face template enrolled; the uploaded image was not retained"}


@router.delete("/{employee_code}/biometrics", status_code=status.HTTP_204_NO_CONTENT)
def revoke_biometric_consent(employee_code: str, db: Session = Depends(get_db)) -> None:
    employee = db.query(Employee).filter(Employee.employee_code == employee_code).first()
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found")
    employee.biometric_consent = False
    employee.consent_timestamp = None
    employee.face_embedding = None
    db.commit()
