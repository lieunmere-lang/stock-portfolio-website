from __future__ import annotations

import logging
import os
import secrets as _secrets
from collections import defaultdict
from datetime import datetime, timedelta
from time import time

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, Request, status
from jose import jwt
from pydantic import BaseModel

logger = logging.getLogger(__name__)

load_dotenv()

APP_USERNAME = os.getenv("APP_USERNAME", "portfolio")
APP_PASSWORD = os.getenv("APP_PASSWORD", "portfolio")

_default_jwt_secret = _secrets.token_hex(32)
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", _default_jwt_secret)
if not os.getenv("JWT_SECRET_KEY"):
    logger.warning("JWT_SECRET_KEY not set — using random key (tokens won't survive restart)")

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7

router = APIRouter(prefix="/auth")

# --------------- Rate Limiting ---------------
_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_ATTEMPTS = 5
_WINDOW_SECONDS = 300  # 5 minutes


def _check_rate_limit(client_ip: str) -> bool:
    """Returns True if rate limited."""
    now = time()
    attempts = _login_attempts[client_ip]
    # Clean old attempts
    _login_attempts[client_ip] = [t for t in attempts if now - t < _WINDOW_SECONDS]
    if len(_login_attempts[client_ip]) >= _MAX_ATTEMPTS:
        return True
    _login_attempts[client_ip].append(now)
    return False


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


def create_access_token(subject: str) -> str:
    expire = datetime.utcnow() + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> str:
    """토큰 검증. 실패 시 HTTPException 발생."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
        return payload["sub"]
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="유효하지 않은 토큰입니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )


@router.post("/token", response_model=TokenResponse)
def login(body: LoginRequest, request: Request):
    client_ip = request.client.host if request.client else "unknown"
    if _check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts. Try again later.",
        )
    valid = (
        _secrets.compare_digest(body.username, APP_USERNAME)
        and _secrets.compare_digest(body.password, APP_PASSWORD)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 잘못되었습니다.",
        )
    token = create_access_token(subject=body.username)
    return {"access_token": token, "token_type": "bearer"}
