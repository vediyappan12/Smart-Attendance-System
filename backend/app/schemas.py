from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from .models import AnomalyType, AttendanceStatus


class EmployeeCreate(BaseModel):
    employee_code: str = Field(min_length=1, max_length=50, pattern=r"^[A-Za-z0-9_-]+$")
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    department: str = Field(min_length=1, max_length=80)
    biometric_consent: bool = False


class SelfRegistration(BaseModel):
    full_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    department: str = Field(min_length=1, max_length=80)
    biometric_consent: Literal[True]
    image_base64: str = Field(min_length=1, max_length=7_000_000)


class AdminLogin(BaseModel):
    username: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=256)


class AdminLoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: int


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    employee_code: str
    full_name: str
    email: EmailStr
    department: str
    is_active: bool
    biometric_consent: bool
    consent_timestamp: datetime | None
    has_biometric: bool


class RegisterFacePayload(BaseModel):
    employee_code: str = Field(min_length=1, max_length=50)
    image_base64: str = Field(min_length=1, max_length=7_000_000)


class VerifyAttendancePayload(RegisterFacePayload):
    image_base64: str | None = Field(default=None, max_length=7_000_000)
    manual_override: bool = False


class CheckoutPayload(BaseModel):
    employee_code: str = Field(min_length=1, max_length=50)


class FaceAttendancePayload(RegisterFacePayload):
    pass


class AttendanceUpdate(BaseModel):
    check_in: datetime | None = None
    check_out: datetime | None = None
    status: AttendanceStatus | None = None
    anomaly_flag: bool | None = None
    anomaly_reason: AnomalyType | None = None
    anomaly_notes: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_times(self) -> "AttendanceUpdate":
        for required_field in ("check_in", "status", "anomaly_flag", "anomaly_reason"):
            if required_field in self.model_fields_set and getattr(self, required_field) is None:
                raise ValueError(f"{required_field} cannot be null")
        if self.check_in and self.check_out and self.check_out < self.check_in:
            raise ValueError("check_out must not be earlier than check_in")
        return self


class AttendanceReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: date
    employee_code: str
    full_name: str
    department: str
    check_in: datetime
    check_out: datetime | None
    status: AttendanceStatus
    verified_via_face: bool
    anomaly_flag: bool
    anomaly_reason: AnomalyType
    anomaly_notes: str | None
