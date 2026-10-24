from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL, make_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    DB_USER: str = "attendance_user"
    DB_PASSWORD: str = ""
    DB_HOST: str = "127.0.0.1"
    DB_PORT: int = 3306
    DB_NAME: str = "attendance_db"
    DATABASE_URL: str = ""
    ADMIN_API_KEY: str = ""
    ADMIN_USERNAME: str = ""
    ADMIN_PASSWORD: str = ""
    BIOMETRIC_ENCRYPTION_KEY: str = ""
    WORK_START_TIME: str = "09:30:00"
    GRACE_PERIOD_MINUTES: int = 15
    CORS_ORIGINS: str = "http://localhost:8000,http://127.0.0.1:8000"

    @field_validator("WORK_START_TIME")
    @classmethod
    def validate_work_start_time(cls, value: str) -> str:
        from datetime import datetime

        datetime.strptime(value, "%H:%M:%S")
        return value

    @field_validator("GRACE_PERIOD_MINUTES")
    @classmethod
    def validate_grace_period(cls, value: int) -> int:
        if not 0 <= value <= 240:
            raise ValueError("GRACE_PERIOD_MINUTES must be between 0 and 240")
        return value

    @property
    def database_url(self) -> URL:
        if self.DATABASE_URL.strip():
            return make_url(self.DATABASE_URL.strip())
        return URL.create(
            "mysql+pymysql",
            username=self.DB_USER,
            password=self.DB_PASSWORD,
            host=self.DB_HOST,
            port=self.DB_PORT,
            database=self.DB_NAME,
            query={"charset": "utf8mb4"},
        )

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


settings = Settings()
