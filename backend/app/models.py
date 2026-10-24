import enum
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    LATE = "LATE"
    HALF_DAY = "HALF_DAY"
    ABSENT = "ABSENT"


class AnomalyType(str, enum.Enum):
    NONE = "NONE"
    GEO_MISMATCH = "GEO_MISMATCH"
    RAPID_REENTRY = "RAPID_REENTRY"
    AFTER_HOURS = "AFTER_HOURS"
    MULTIPLE_FACES = "MULTIPLE_FACES"


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    department: Mapped[str] = mapped_column(String(80), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    biometric_consent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    consent_timestamp: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    face_embedding: Mapped[str | None] = mapped_column(Text, nullable=True)

    attendances: Mapped[list["Attendance"]] = relationship(back_populates="employee")

    @property
    def has_biometric(self) -> bool:
        return self.face_embedding is not None


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), nullable=False, index=True)
    date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False, index=True)
    check_in: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    check_out: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[AttendanceStatus] = mapped_column(
        Enum(AttendanceStatus), default=AttendanceStatus.PRESENT, nullable=False
    )
    verified_via_face: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_flag: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    anomaly_reason: Mapped[AnomalyType] = mapped_column(
        Enum(AnomalyType), default=AnomalyType.NONE, nullable=False
    )
    anomaly_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    employee: Mapped[Employee] = relationship(back_populates="attendances")
