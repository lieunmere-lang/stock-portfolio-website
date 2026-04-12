from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict, List, Optional

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
    first_purchase_date: Any = None
    signed_change_price: float = 0
    signed_change_rate: float = 0
    currency: str = "KRW"
    avg_price_usd: Optional[float] = None
    current_price_usd: Optional[float] = None


class PortfolioOut(BaseModel):
    last_synced: str
    total_value: float
    total_investment: float
    total_profit_loss: float
    total_profit_loss_rate: float
    today_profit_loss: Any  # Optional[float]
    assets: List[AssetOut]
    sync_error: Any = None  # 동기화 실패 메시지


@router.get("/portfolio", response_model=PortfolioOut)
def get_portfolio():
    cache = get_portfolio_cache()
    if not cache:
        sync_portfolio()
        cache = get_portfolio_cache()
    # sync 실패해도 빈 포트폴리오로 응답 (500 대신 200)
    if not cache:
        cache = {
            "last_synced": "—",
            "total_value": 0.0,
            "total_investment": 0.0,
            "total_profit_loss": 0.0,
            "total_profit_loss_rate": 0.0,
            "today_profit_loss": None,
            "assets": [],
            "sync_error": "포트폴리오 데이터를 불러올 수 없습니다.",
        }
    return cache


@router.post("/sync")
def force_sync():
    sync_portfolio()
    cache = get_portfolio_cache()
    error = cache.get("sync_error") if cache else None
    if error:
        return {"status": "error", "message": error}
    return {"status": "success", "message": "동기화 완료"}
