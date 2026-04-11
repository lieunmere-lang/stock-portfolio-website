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
