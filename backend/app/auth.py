import base64
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

bearer_scheme = HTTPBearer(auto_error=False)
TOKEN_LIFETIME_SECONDS = 8 * 60 * 60


def _encode_token(payload: dict[str, object]) -> str:
    encoded = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).rstrip(b"=")
    signature = hmac.new(settings.ADMIN_API_KEY.encode(), encoded, hashlib.sha256).digest()
    return encoded.decode() + "." + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def _decode_token(token: str) -> dict[str, object]:
    try:
        encoded, supplied_signature = token.split(".", 1)
        expected_signature = hmac.new(
            settings.ADMIN_API_KEY.encode(), encoded.encode(), hashlib.sha256
        ).digest()
        decoded_signature = base64.urlsafe_b64decode(supplied_signature + "=" * (-len(supplied_signature) % 4))
        if not hmac.compare_digest(expected_signature, decoded_signature):
            raise ValueError("Invalid token signature")
        payload = json.loads(base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)))
        if not isinstance(payload, dict) or payload.get("exp", 0) < time.time():
            raise ValueError("Expired token")
        return payload
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session is invalid or expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def create_admin_token(username: str) -> tuple[str, int]:
    expires_at = int(time.time()) + TOKEN_LIFETIME_SECONDS
    return _encode_token({"sub": username, "exp": expires_at}), expires_at


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> None:
    if not settings.ADMIN_API_KEY or not settings.ADMIN_USERNAME or not settings.ADMIN_PASSWORD:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Configure admin login credentials and token secret in backend/.env",
        )
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin login is required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = _decode_token(credentials.credentials)
    if payload.get("sub") != settings.ADMIN_USERNAME:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Admin session is invalid",
            headers={"WWW-Authenticate": "Bearer"},
        )


def verify_admin_credentials(username: str, password: str) -> bool:
    return bool(
        settings.ADMIN_USERNAME
        and settings.ADMIN_PASSWORD
        and settings.ADMIN_API_KEY
        and secrets.compare_digest(username.encode(), settings.ADMIN_USERNAME.encode())
        and secrets.compare_digest(password.encode(), settings.ADMIN_PASSWORD.encode())
    )
