from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from . import models  # noqa: F401 - registers SQLAlchemy models with Base.metadata
from .config import settings
from .database import Base, engine, get_db
from .routers import attendance, employees, public, reports
from .routers import authentication


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Smart Attendance Management API",
    version="1.0.0",
    description="Employee attendance, anomaly monitoring, and consent-based optional face verification.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(employees.router)
app.include_router(attendance.router)
app.include_router(reports.router)
app.include_router(public.router)
app.include_router(authentication.router)


@app.get("/api/health", tags=["health"])
def health(db: Session = Depends(get_db)) -> dict[str, str | bool]:
    db.execute(text("SELECT 1"))
    try:
        import face_recognition  # noqa: F401
    except ImportError:
        face_ready = False
    else:
        face_ready = True
    return {"status": "ok", "database": "connected", "face_recognition_ready": face_ready}


@app.get("/admin", include_in_schema=False)
def admin_page() -> FileResponse:
    return FileResponse(Path(__file__).resolve().parents[2] / "frontend" / "admin.html")


frontend_dir = Path(__file__).resolve().parents[2] / "frontend"
app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="frontend")
