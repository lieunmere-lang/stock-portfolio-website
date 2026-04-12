from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError

from database import init_db
from routers.analytics import router as analytics_router
from routers.auth import router as auth_router, verify_token
from routers.coin import router as coin_router
from routers.market import router as market_router
from routers.news import router as news_router
from routers.stock import router as stock_router
from routers.portfolio import router as portfolio_router
from routers.rebalance import router as rebalance_router
from routers.journal import router as journal_router
from routers.alerts import router as alerts_router
from scheduler import start_scheduler, stop_scheduler
from bot import start_bot, stop_bot

FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    init_db()
    start_scheduler()
    await start_bot()
    yield
    # shutdown
    await stop_bot()
    stop_scheduler()


app = FastAPI(title="Portfolio API", lifespan=lifespan)

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
app.include_router(auth_router)                                              # /auth/token (인증 불필요)
app.include_router(portfolio_router, dependencies=[Depends(require_auth)])   # /api/portfolio (인증 필요)
app.include_router(analytics_router, dependencies=[Depends(require_auth)])   # /api/analytics/* (인증 필요)
app.include_router(coin_router,      dependencies=[Depends(require_auth)])   # /api/coin/* (인증 필요)
app.include_router(stock_router,     dependencies=[Depends(require_auth)])   # /api/stock/* (인증 필요)
app.include_router(news_router,      dependencies=[Depends(require_auth)])   # /api/news/* (인증 필요)
app.include_router(market_router,    dependencies=[Depends(require_auth)])   # /api/market/* (인증 필요)
app.include_router(rebalance_router, dependencies=[Depends(require_auth)])   # /api/rebalance/* (인증 필요)
app.include_router(journal_router,   dependencies=[Depends(require_auth)])   # /api/journal/* (인증 필요)
app.include_router(alerts_router,    dependencies=[Depends(require_auth)])   # /api/alerts/* (인증 필요)



# ── 헬스체크 ─────────────────────────────────────────────────────────────
@app.get("/health")
def health():
    return {"status": "ok"}


# ── 정적 파일 서빙 (반드시 맨 마지막에 마운트) ──────────────────────────
app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
