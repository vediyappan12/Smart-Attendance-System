from fastapi import APIRouter, HTTPException, status

from ..auth import create_admin_token, verify_admin_credentials
from ..schemas import AdminLogin, AdminLoginResponse

router = APIRouter(prefix="/api/auth", tags=["admin authentication"])


@router.post("/login", response_model=AdminLoginResponse)
def admin_login(credentials: AdminLogin) -> AdminLoginResponse:
    if not verify_admin_credentials(credentials.username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid admin username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_at = create_admin_token(credentials.username)
    return AdminLoginResponse(access_token=token, expires_at=expires_at)
