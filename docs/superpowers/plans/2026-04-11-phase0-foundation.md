# Phase 0 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 기존 Basic Auth + 분리된 프론트엔드 서버 구조를 JWT 로그인 페이지 + SQLite DB + 통합 FastAPI 서버로 교체하여 모바일 접속이 편리하고 이력 데이터를 저장할 수 있는 기반을 만든다.

**Architecture:** FastAPI가 JWT 인증·API·정적 파일 서빙을 모두 담당한다. 별도 `frontend_server.py`를 제거하고 ngrok/Cloudflare는 포트 8000만 바라본다. SQLite(WAL 모드)로 포트폴리오 스냅샷을 영구 저장하여 수익률 이력 차트 기반을 마련한다.

**Tech Stack:** FastAPI, SQLAlchemy (sync), SQLite WAL, python-jose (JWT HS256), Bootstrap 5, Chart.js

---

## 파일 변경 맵

```
생성
  .gitignore
  backend/database.py          # SQLAlchemy 모델 + DB 초기화
  backend/routers/__init__.py  # 빈 파일
  backend/routers/auth.py      # POST /auth/token (JWT 발급)
  backend/routers/portfolio.py # GET /api/portfolio, POST /api/sync
  backend/services/__init__.py # 빈 파일
  backend/services/upbit.py    # 업비트 연동 로직
  backend/scheduler.py         # APScheduler 작업 정의
  frontend/login.html          # JWT 로그인 폼

수정
  backend/main.py              # 슬림하게 재작성 (라우터 연결, 정적 파일)
  backend/requirements.txt     # sqlalchemy, python-jose 추가
  backend/.env                 # JWT_SECRET_KEY 추가
  frontend/index.html          # JWT Bearer 인증으로 교체
  manage_server.sh             # TUNNEL_PORT 8001→8000, frontend 서버 제거

삭제
  frontend/frontend_server.py  # FastAPI가 정적 파일 서빙을 대체
```

---

## Task 1: .gitignore 생성

**Files:**
- Create: `.gitignore`

- [ ] **Step 1: .gitignore 파일 생성**

```gitignore
# Python
__pycache__/
*.py[cod]
*.pyo
venv/
.venv/
*.egg-info/

# Environment & Secrets
.env
*.env

# Server runtime
*.pid
*.log
server.log
frontend.log
ngrok.log

# SQLite
*.db
*.db-shm
*.db-wal

# macOS
.DS_Store

# IDE
.vscode/
.idea/
```

- [ ] **Step 2: 커밋**

```bash
git add .gitignore
git commit -m "chore: add .gitignore"
```

---

## Task 2: requirements.txt 업데이트

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: 의존성 추가**

`backend/requirements.txt` 전체를 아래로 교체:

```
fastapi
uvicorn[standard]
requests
apscheduler
python-dotenv
pyjwt
sqlalchemy
python-jose[cryptography]
```

> `python-jose`는 FastAPI 공식 JWT 예제에서 사용하는 라이브러리. `pyjwt`(기존)는 업비트 API 서명에만 계속 사용.

- [ ] **Step 2: 가상환경에 설치**

```bash
cd backend && venv/bin/pip install -r requirements.txt
```

Expected: Successfully installed ... (오류 없음)

- [ ] **Step 3: 커밋**

```bash
git add backend/requirements.txt
git commit -m "chore: add sqlalchemy and python-jose dependencies"
```

---

## Task 3: .env에 JWT_SECRET_KEY 추가

**Files:**
- Modify: `backend/.env`

- [ ] **Step 1: 랜덤 시크릿 생성**

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

출력된 64자리 16진수 문자열을 복사.

- [ ] **Step 2: .env에 추가**

`backend/.env` 파일 맨 아래에 한 줄 추가:

```
JWT_SECRET_KEY=<위에서 복사한 값>
```

> .gitignore에 `.env`가 포함되어 있으므로 커밋하지 않음. 변경사항만 로컬에 저장.

---

## Task 4: SQLite 데이터베이스 모델 (database.py)

**Files:**
- Create: `backend/database.py`

- [ ] **Step 1: database.py 생성**

```python
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship

load_dotenv()

DB_PATH = Path(__file__).resolve().parent / "portfolio.db"
DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


@event.listens_for(engine, "connect")
def set_wal_mode(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.close()


class Base(DeclarativeBase):
    pass


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"

    id = Column(Integer, primary_key=True)
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False)
    total_value = Column(Float, nullable=False)
    total_profit_loss = Column(Float, nullable=False)
    total_profit_loss_rate = Column(Float, nullable=False)

    assets = relationship("AssetSnapshot", back_populates="snapshot", cascade="all, delete-orphan")


class AssetSnapshot(Base):
    __tablename__ = "asset_snapshots"

    id = Column(Integer, primary_key=True)
    snapshot_id = Column(Integer, ForeignKey("portfolio_snapshots.id"), nullable=False)
    name = Column(String(50), nullable=False)
    ticker = Column(String(20), nullable=False)
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)
    current_price = Column(Float, nullable=False)
    total_value = Column(Float, nullable=False)
    profit_loss = Column(Float, nullable=False)
    profit_loss_rate = Column(Float, nullable=False)
    asset_type = Column(String(20), nullable=False, default="crypto")

    snapshot = relationship("PortfolioSnapshot", back_populates="assets")


class NewsReport(Base):
    __tablename__ = "news_reports"

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    category = Column(String(50), nullable=False)
    title = Column(Text, nullable=False)
    summary = Column(Text)
    source = Column(String(100))
    url = Column(Text)


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    condition = Column(String(10), nullable=False)   # "above" | "below"
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)


def init_db():
    Base.metadata.create_all(bind=engine)


def get_db():
    with Session(engine) as session:
        yield session
```

- [ ] **Step 2: DB 초기화 동작 확인**

```bash
cd backend && venv/bin/python -c "from database import init_db; init_db(); print('OK')"
```

Expected: `OK` 출력, `backend/portfolio.db` 파일 생성됨.

```bash
ls -la backend/portfolio.db
```

- [ ] **Step 3: WAL 모드 확인**

```bash
cd backend && venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('portfolio.db')
print(conn.execute('PRAGMA journal_mode').fetchone())
conn.close()
"
```

Expected: `('wal',)`

- [ ] **Step 4: 커밋**

```bash
git add backend/database.py
git commit -m "feat: add SQLite database with WAL mode and SQLAlchemy models"
```

---

## Task 5: 업비트 서비스 분리 (services/upbit.py)

**Files:**
- Create: `backend/services/__init__.py`
- Create: `backend/services/upbit.py`

- [ ] **Step 1: __init__.py 생성**

```python
# backend/services/__init__.py
```

(빈 파일)

- [ ] **Step 2: services/upbit.py 생성**

```python
import os
import uuid
from typing import Any, Dict, List

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")


def fetch_upbit_assets() -> List[Dict[str, Any]]:
    """업비트 계정의 보유 코인 목록과 현재가를 반환한다."""
    if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
        print("Upbit API keys not set. Skipping fetch.")
        return []

    payload = {"access_key": UPBIT_ACCESS_KEY, "nonce": str(uuid.uuid4())}
    token = jwt.encode(payload, UPBIT_SECRET_KEY)
    headers = {"Authorization": f"Bearer {token}"}

    res = requests.get("https://api.upbit.com/v1/accounts", headers=headers, timeout=10)
    res.raise_for_status()
    my_assets = res.json()

    tickers = [a["currency"] for a in my_assets if a["currency"] != "KRW"]
    if not tickers:
        return []

    upbit_tickers = [f"KRW-{t}" for t in tickers]
    ticker_res = requests.get(
        f"https://api.upbit.com/v1/ticker?markets={','.join(upbit_tickers)}",
        timeout=10,
    )
    ticker_res.raise_for_status()
    ticker_map = {t["market"]: t for t in ticker_res.json()}

    result = []
    for asset in my_assets:
        currency = asset["currency"]
        if currency == "KRW":
            continue
        market = f"KRW-{currency}"
        price_info = ticker_map.get(market)
        if not price_info:
            continue
        result.append(
            {
                "name": currency,
                "ticker": market,
                "quantity": float(asset["balance"]),
                "avg_price": float(asset["avg_buy_price"]),
                "current_price": float(price_info["trade_price"]),
            }
        )
    return result
```

- [ ] **Step 3: import 동작 확인**

```bash
cd backend && venv/bin/python -c "from services.upbit import fetch_upbit_assets; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 4: 커밋**

```bash
git add backend/services/
git commit -m "refactor: extract Upbit API logic into services/upbit.py"
```

---

## Task 6: 스케줄러 분리 (scheduler.py)

**Files:**
- Create: `backend/scheduler.py`

- [ ] **Step 1: scheduler.py 생성**

```python
from datetime import datetime
from typing import Any, Dict, List

from apscheduler.schedulers.background import BackgroundScheduler

from database import AssetSnapshot, PortfolioSnapshot, Session, engine
from services.upbit import fetch_upbit_assets

scheduler = BackgroundScheduler()

# 현재 포트폴리오 상태를 계산하여 메모리 캐시와 DB에 저장한다.
_portfolio_cache: Dict[str, Any] = {}


def get_portfolio_cache() -> Dict[str, Any]:
    return _portfolio_cache


def sync_portfolio() -> None:
    global _portfolio_cache
    print(f"[{datetime.now().isoformat()}] Syncing portfolio...")

    raw_assets = fetch_upbit_assets()

    total_value = 0.0
    total_purchase = 0.0
    asset_rows = []

    for a in raw_assets:
        qty = a["quantity"]
        avg = a["avg_price"]
        cur = a["current_price"]
        val = qty * cur
        pl = (cur - avg) * qty
        plr = (cur / avg - 1) if avg > 0 else 0.0

        total_value += val
        total_purchase += qty * avg
        asset_rows.append(
            {
                "name": a["name"],
                "ticker": a["ticker"],
                "quantity": qty,
                "avg_price": avg,
                "current_price": cur,
                "total_value": val,
                "profit_loss": pl,
                "profit_loss_rate": plr,
                "asset_type": "crypto",
            }
        )

    total_pl = total_value - total_purchase
    total_plr = (total_value / total_purchase - 1) if total_purchase > 0 else 0.0

    # 메모리 캐시 갱신
    _portfolio_cache = {
        "last_synced": datetime.now().isoformat(),
        "total_value": total_value,
        "total_profit_loss": total_pl,
        "total_profit_loss_rate": total_plr,
        "assets": asset_rows,
    }

    # DB 스냅샷 저장
    with Session(engine) as db:
        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            total_value=total_value,
            total_profit_loss=total_pl,
            total_profit_loss_rate=total_plr,
        )
        db.add(snapshot)
        db.flush()
        for a in asset_rows:
            db.add(AssetSnapshot(snapshot_id=snapshot.id, **a))
        db.commit()

    print("Sync complete.")


def start_scheduler():
    scheduler.add_job(sync_portfolio, "interval", hours=1, id="portfolio_sync")
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown()
```

- [ ] **Step 2: import 확인**

```bash
cd backend && venv/bin/python -c "from scheduler import sync_portfolio; print('import OK')"
```

Expected: `import OK`

- [ ] **Step 3: 커밋**

```bash
git add backend/scheduler.py
git commit -m "refactor: extract APScheduler logic into scheduler.py with DB snapshot saving"
```

---

## Task 7: 포트폴리오 라우터 (routers/portfolio.py)

**Files:**
- Create: `backend/routers/__init__.py`
- Create: `backend/routers/portfolio.py`

- [ ] **Step 1: __init__.py 생성**

```python
# backend/routers/__init__.py
```

(빈 파일)

- [ ] **Step 2: routers/portfolio.py 생성**

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List

from scheduler import get_portfolio_cache, sync_portfolio

router = APIRouter(prefix="/api")


class AssetOut(BaseModel):
    name: str
    ticker: str
    quantity: float
    avg_price: float
    current_price: float
    total_value: float
    profit_loss: float
    profit_loss_rate: float
    asset_type: str = "crypto"


class PortfolioOut(BaseModel):
    last_synced: str
    total_value: float
    total_profit_loss: float
    total_profit_loss_rate: float
    assets: List[AssetOut]


@router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio():
    cache = get_portfolio_cache()
    if not cache:
        sync_portfolio()
        cache = get_portfolio_cache()
    if not cache:
        raise HTTPException(status_code=503, detail="포트폴리오 데이터를 불러올 수 없습니다.")
    return cache


@router.post("/sync")
def force_sync():
    sync_portfolio()
    return {"status": "success", "message": "동기화 완료"}
```

- [ ] **Step 3: 커밋**

```bash
git add backend/routers/
git commit -m "refactor: add portfolio router"
```

---

## Task 8: JWT 인증 라우터 (routers/auth.py)

**Files:**
- Create: `backend/routers/auth.py`

- [ ] **Step 1: auth.py 생성**

```python
import os
import secrets
from datetime import datetime, timedelta

from dotenv import load_dotenv
from fastapi import APIRouter, HTTPException, status
from jose import jwt
from pydantic import BaseModel

load_dotenv()

APP_USERNAME = os.getenv("APP_USERNAME", "portfolio")
APP_PASSWORD = os.getenv("APP_PASSWORD", "portfolio")
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 30

router = APIRouter(prefix="/auth")


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
def login(body: LoginRequest):
    valid = (
        secrets.compare_digest(body.username, APP_USERNAME)
        and secrets.compare_digest(body.password, APP_PASSWORD)
    )
    if not valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="아이디 또는 비밀번호가 잘못되었습니다.",
        )
    token = create_access_token(subject=body.username)
    return {"access_token": token, "token_type": "bearer"}
```

- [ ] **Step 2: token 발급 로직 단위 검증**

```bash
cd backend && venv/bin/python -c "
from routers.auth import create_access_token, verify_token
token = create_access_token('testuser')
subject = verify_token(token)
assert subject == 'testuser', f'expected testuser, got {subject}'
print('JWT round-trip OK')
"
```

Expected: `JWT round-trip OK`

- [ ] **Step 3: 커밋**

```bash
git add backend/routers/auth.py
git commit -m "feat: add JWT auth router with 30-day token expiry"
```

---

## Task 9: main.py 재작성

**Files:**
- Modify: `backend/main.py` (전체 재작성)

현재 main.py는 모든 로직이 한 파일에 있음. 라우터와 서비스로 분리한 뒤 main.py는 앱 조립만 담당.

- [ ] **Step 1: main.py 전체 교체**

```python
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError

from database import init_db
from routers.auth import router as auth_router, verify_token
from routers.portfolio import router as portfolio_router
from scheduler import start_scheduler, stop_scheduler

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"

app = FastAPI(title="Portfolio API")

# CORS: 로컬 개발 + 동일 origin 허용 (ngrok/Cloudflare는 same-origin으로 접근)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── JWT 의존성 ────────────────────────────────────────────────────────────
def require_auth(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header.removeprefix("Bearer ").strip()
    return verify_token(token)


# ── 라우터 등록 ───────────────────────────────────────────────────────────
app.include_router(auth_router)                         # /auth/token (인증 불필요)
app.include_router(portfolio_router, dependencies=[Depends(require_auth)])  # /api/* (인증 필요)


# ── 수명 주기 ─────────────────────────────────────────────────────────────
@app.on_event("startup")
def startup():
    init_db()
    start_scheduler()


@app.on_event("shutdown")
def shutdown():
    stop_scheduler()


# ── 헬스체크 ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ── 정적 파일 서빙 (반드시 맨 마지막에 마운트) ──────────────────────────
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
```

- [ ] **Step 2: 서버 시작 확인**

```bash
cd backend && venv/bin/uvicorn main:app --port 8000 --reload &
sleep 3
curl -s http://127.0.0.1:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: /auth/token 동작 확인**

```bash
curl -s -X POST http://127.0.0.1:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"daehyeon.park","password":"eogus102@@"}' | python3 -m json.tool
```

Expected: `access_token` 필드 포함 JSON 응답

- [ ] **Step 4: 인증 없이 /api/portfolio 접근 시 401 확인**

```bash
curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/api/portfolio
```

Expected: `401`

- [ ] **Step 5: 서버 종료 후 커밋**

```bash
kill %1
git add backend/main.py
git commit -m "refactor: rewrite main.py to use JWT auth and modular routers"
```

---

## Task 10: 로그인 페이지 (frontend/login.html)

**Files:**
- Create: `frontend/login.html`

- [ ] **Step 1: login.html 생성**

```html
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>포트폴리오 로그인</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    body {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      min-height: 100vh;
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Inter', sans-serif;
    }
    .login-card {
      background: white;
      border-radius: 1rem;
      box-shadow: 0 20px 60px rgba(0,0,0,0.15);
      padding: 2.5rem;
      width: 100%;
      max-width: 400px;
    }
    .login-title {
      font-size: 1.5rem;
      font-weight: 700;
      color: #1a1a2e;
    }
    .btn-login {
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
      border: none;
      color: white;
      font-weight: 600;
    }
    .btn-login:hover { opacity: 0.9; color: white; }
    #error-msg { display: none; }
  </style>
</head>
<body>
  <div class="login-card">
    <div class="text-center mb-4">
      <div style="font-size:2.5rem;">📈</div>
      <div class="login-title mt-2">My Portfolio</div>
      <small class="text-muted">개인 투자 대시보드</small>
    </div>

    <div id="error-msg" class="alert alert-danger py-2 small"></div>

    <form id="login-form">
      <div class="mb-3">
        <label class="form-label fw-semibold">아이디</label>
        <input id="username" type="text" class="form-control" placeholder="username" autocomplete="username" required>
      </div>
      <div class="mb-4">
        <label class="form-label fw-semibold">비밀번호</label>
        <input id="password" type="password" class="form-control" placeholder="••••••••" autocomplete="current-password" required>
      </div>
      <button type="submit" class="btn btn-login w-100 py-2">
        <span id="btn-text">로그인</span>
        <span id="btn-spinner" class="spinner-border spinner-border-sm ms-2 d-none"></span>
      </button>
    </form>
  </div>

  <script>
    // 이미 토큰이 있으면 대시보드로 이동
    if (localStorage.getItem('portfolio_token')) {
      window.location.href = '/';
    }

    const form = document.getElementById('login-form');
    const errorMsg = document.getElementById('error-msg');
    const btnText = document.getElementById('btn-text');
    const btnSpinner = document.getElementById('btn-spinner');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      errorMsg.style.display = 'none';
      btnText.textContent = '로그인 중...';
      btnSpinner.classList.remove('d-none');

      const username = document.getElementById('username').value.trim();
      const password = document.getElementById('password').value;

      try {
        const res = await fetch('/auth/token', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ username, password }),
        });

        if (!res.ok) {
          const data = await res.json().catch(() => ({}));
          throw new Error(data.detail || '로그인 실패');
        }

        const { access_token } = await res.json();
        localStorage.setItem('portfolio_token', access_token);
        window.location.href = '/';
      } catch (err) {
        errorMsg.textContent = err.message;
        errorMsg.style.display = 'block';
      } finally {
        btnText.textContent = '로그인';
        btnSpinner.classList.add('d-none');
      }
    });
  </script>
</body>
</html>
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/login.html
git commit -m "feat: add JWT login page"
```

---

## Task 11: index.html JWT 인증으로 교체

**Files:**
- Modify: `frontend/index.html`

index.html에서 Basic Auth 관련 코드를 제거하고 JWT Bearer 헤더를 사용하도록 수정한다.

- [ ] **Step 1: 상단 `<script>` 블록의 인증 관련 변수 교체**

아래 3줄을 찾아서:
```javascript
const API_URL = '/api/portfolio';
const SYNC_URL = '/api/sync';
const API_AUTH_HEADER = '__BASIC_AUTH_HEADER__';
```

아래로 교체:
```javascript
const API_URL = '/api/portfolio';
const SYNC_URL = '/api/sync';

function getAuthHeaders() {
  const token = localStorage.getItem('portfolio_token');
  if (!token) {
    window.location.href = '/login.html';
    return null;
  }
  return { 'Authorization': `Bearer ${token}` };
}
```

- [ ] **Step 2: fetchPortfolio 함수 내 fetch 호출 교체**

아래를 찾아서:
```javascript
const response = await fetch(API_URL, {
    credentials: 'same-origin',
    headers: API_AUTH_HEADER && API_AUTH_HEADER !== '__BASIC_AUTH_HEADER__'
        ? { Authorization: API_AUTH_HEADER }
        : {},
});
if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
}
```

아래로 교체:
```javascript
const headers = getAuthHeaders();
if (!headers) return;
const response = await fetch(API_URL, { headers });
if (response.status === 401) {
    localStorage.removeItem('portfolio_token');
    window.location.href = '/login.html';
    return;
}
if (!response.ok) {
    throw new Error(`HTTP error! status: ${response.status}`);
}
```

- [ ] **Step 3: forceSync 함수 내 fetch 호출 교체**

아래를 찾아서:
```javascript
const response = await fetch(SYNC_URL, {
    method: 'POST',
    credentials: 'same-origin',
    headers: API_AUTH_HEADER && API_AUTH_HEADER !== '__BASIC_AUTH_HEADER__'
        ? { Authorization: API_AUTH_HEADER }
        : {},
});
```

아래로 교체:
```javascript
const headers = getAuthHeaders();
if (!headers) return;
const response = await fetch(SYNC_URL, { method: 'POST', headers });
if (response.status === 401) {
    localStorage.removeItem('portfolio_token');
    window.location.href = '/login.html';
    return;
}
```

- [ ] **Step 4: 네비게이션 바에 로그아웃 버튼 추가**

`<div class="d-flex align-items-center">` 안의 기존 내용 뒤에 추가:
```html
<button onclick="logout()" class="btn btn-outline-secondary btn-sm ms-2">로그아웃</button>
```

스크립트 맨 아래에 추가:
```javascript
function logout() {
  localStorage.removeItem('portfolio_token');
  window.location.href = '/login.html';
}
```

- [ ] **Step 5: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: replace Basic Auth with JWT Bearer token in index.html"
```

---

## Task 12: manage_server.sh 단순화

**Files:**
- Modify: `manage_server.sh`

frontend_server.py 제거로 인해 터널이 포트 8000(백엔드)을 직접 바라보도록 변경.

- [ ] **Step 1: TUNNEL_PORT와 start_all 수정**

아래를 찾아서:
```bash
TUNNEL_PORT="$FRONTEND_PORT"
```

아래로 교체:
```bash
TUNNEL_PORT="$PORT"
```

- [ ] **Step 2: start_all에서 frontend 서버 제거**

아래를 찾아서:
```bash
function start_all() {
    start_server
    start_frontend_server
    if ! start_tunnel; then
```

아래로 교체:
```bash
function start_all() {
    start_server
    if ! start_tunnel; then
```

- [ ] **Step 3: stop_all에서 frontend 서버 제거**

아래를 찾아서:
```bash
function stop_all() {
    stop_tunnel
    stop_frontend_server
    stop_server
}
```

아래로 교체:
```bash
function stop_all() {
    stop_tunnel
    stop_server
}
```

- [ ] **Step 4: status_all에서 frontend 상태 제거**

아래를 찾아서:
```bash
function status_all() {
    status_server
    status_frontend
    status_tunnel
}
```

아래로 교체:
```bash
function status_all() {
    status_server
    status_tunnel
}
```

- [ ] **Step 5: 전체 시작 테스트**

```bash
./manage_server.sh start-backend
sleep 3
./manage_server.sh status
```

Expected: `Backend is running.` 출력

- [ ] **Step 6: 커밋**

```bash
git add manage_server.sh
git commit -m "chore: simplify manage_server.sh — remove frontend server, tunnel points to port 8000"
```

---

## Task 13: frontend_server.py 제거

**Files:**
- Delete: `frontend/frontend_server.py`

- [ ] **Step 1: 삭제**

```bash
git rm frontend/frontend_server.py
git commit -m "chore: remove frontend_server.py (replaced by FastAPI static file serving)"
```

---

## Task 14: 전체 E2E 동작 확인

- [ ] **Step 1: 서버 재시작**

```bash
./manage_server.sh stop
./manage_server.sh start-backend
sleep 3
```

- [ ] **Step 2: 헬스체크**

```bash
curl -s http://127.0.0.1:8000/health
```

Expected: `{"status":"ok"}`

- [ ] **Step 3: 로그인 → 토큰 발급**

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"daehyeon.park","password":"eogus102@@"}' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")
echo "TOKEN: $TOKEN"
```

Expected: 긴 JWT 문자열 출력

- [ ] **Step 4: 토큰으로 포트폴리오 조회**

```bash
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8000/api/portfolio | python3 -m json.tool | head -20
```

Expected: 포트폴리오 JSON (업비트 자산 포함)

- [ ] **Step 5: 브라우저에서 확인**

`http://localhost:8000` 접속 → `login.html` 로 리다이렉트됨을 확인  
→ 아이디·비밀번호 입력 → `index.html` 대시보드로 이동 확인  
→ 로그아웃 버튼 클릭 → 다시 `login.html` 이동 확인

- [ ] **Step 6: DB 스냅샷 저장 확인**

```bash
cd backend && venv/bin/python -c "
import sqlite3
conn = sqlite3.connect('portfolio.db')
count = conn.execute('SELECT COUNT(*) FROM portfolio_snapshots').fetchone()[0]
print(f'Snapshots in DB: {count}')
conn.close()
"
```

Expected: `Snapshots in DB: 1` (또는 이상)

---

## 완료 기준

- [ ] `http://localhost:8000` 접속 시 로그인 페이지 표시
- [ ] 로그인 성공 후 대시보드 정상 표시
- [ ] 401 발생 시 자동으로 로그인 페이지로 이동
- [ ] 로그아웃 버튼 동작
- [ ] `portfolio.db`에 스냅샷 저장됨 (WAL 모드)
- [ ] `frontend_server.py` 삭제됨
- [ ] ngrok이 포트 8000을 터널링함
- [ ] `.gitignore`에 `.env`, `*.db`, `venv/` 포함됨
