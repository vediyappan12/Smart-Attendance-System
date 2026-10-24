from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from .config import settings
from .models import AnomalyType, Attendance, AttendanceStatus


class AnomalyDetector:
    @staticmethod
    def evaluate_checkin(
        db_session: Session, employee_id: int, checkin_time: datetime
    ) -> tuple[bool, AnomalyType, str | None]:
        recent_entry = (
            db_session.query(Attendance)
            .filter(
                Attendance.employee_id == employee_id,
                Attendance.check_in >= checkin_time - timedelta(minutes=10),
                Attendance.check_in <= checkin_time,
            )
            .first()
        )
        if recent_entry:
            return True, AnomalyType.RAPID_REENTRY, "Check-in occurred within 10 minutes of a previous check-in"

        if checkin_time.hour < 6 or checkin_time.hour >= 22:
            return True, AnomalyType.AFTER_HOURS, f"Check-in recorded outside normal hours at {checkin_time:%H:%M}"

        return False, AnomalyType.NONE, None

    @staticmethod
    def determine_punctuality(checkin_time: datetime) -> AttendanceStatus:
        expected_time = datetime.strptime(settings.WORK_START_TIME, "%H:%M:%S").time()
        grace_limit = (
            datetime.combine(checkin_time.date(), expected_time)
            + timedelta(minutes=settings.GRACE_PERIOD_MINUTES)
        ).time()
        return AttendanceStatus.LATE if checkin_time.time() > grace_limit else AttendanceStatus.PRESENT
