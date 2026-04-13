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
ACCESS_TOKEN_EXPIRE_DAYS = 1

router = APIRouter(prefix="/auth")

# --------------- Rate Limiting (progressive backoff) ---------------
_login_attempts: dict[str, list[float]] = defaultdict(list)
_lockout_until: dict[str, float] = {}
_fail_streaks: dict[str, int] = defaultdict(int)

# 5회 실패 → 5분, 10회 → 15분, 15회 → 60분
_THRESHOLDS = [
    (5, 300),     # 5회 → 5분
    (10, 900),    # 10회 → 15분
    (15, 3600),   # 15회 → 60분
]
_MAX_FIRST_WINDOW = 5  # 첫 차단까지 허용 횟수


def _check_rate_limit(client_ip: str) -> tuple[bool, int, int]:
    """Returns (is_limited, remaining_attempts, lockout_seconds)."""
    now = time()

    # 현재 잠금 상태 확인
    if client_ip in _lockout_until:
        remaining_lock = _lockout_until[client_ip] - now
        if remaining_lock > 0:
            return True, 0, int(remaining_lock)
        else:
            del _lockout_until[client_ip]

    streak = _fail_streaks[client_ip]

    # 다음 차단 임계값 확인
    for threshold, lockout in _THRESHOLDS:
        if streak < threshold:
            remaining = threshold - streak - 1
            return False, remaining, 0

    # 모든 임계값 초과 → 최대 잠금
    return True, 0, 3600


def _record_failed_attempt(client_ip: str):
    """실패 기록 및 필요 시 잠금 설정"""
    _fail_streaks[client_ip] += 1
    streak = _fail_streaks[client_ip]

    for threshold, lockout in _THRESHOLDS:
        if streak == threshold:
            _lockout_until[client_ip] = time() + lockout
            logger.warning(f"IP {client_ip} locked out for {lockout}s after {streak} failures")
            break


def _reset_attempts(client_ip: str):
    """로그인 성공 시 초기화"""
    _fail_streaks.pop(client_ip, None)
    _lockout_until.pop(client_ip, None)


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
    is_limited, remaining, lockout_secs = _check_rate_limit(client_ip)
    if is_limited:
        minutes = max(1, lockout_secs // 60)
        raise HTTPException(
            status_code=429,
            detail=f"로그인 시도가 너무 많습니다. {minutes}분 후 다시 시도해주세요.",
        )
    valid = (
        _secrets.compare_digest(body.username, APP_USERNAME)
        and _secrets.compare_digest(body.password, APP_PASSWORD)
    )
    if not valid:
        _record_failed_attempt(client_ip)
        logger.warning(f"Failed login attempt from {client_ip}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 잘못되었습니다.",
        )
    _reset_attempts(client_ip)
    logger.info(f"Successful login from {client_ip}")
    token = create_access_token(subject=body.username)
    return {"access_token": token, "token_type": "bearer"}
