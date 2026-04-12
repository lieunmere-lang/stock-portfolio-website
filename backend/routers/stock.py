"""주식 상세 정보 라우터 — yfinance 기반."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from database import Session, StockHolding, engine
from services.stock import fetch_earnings_calendar, fetch_stock_detail, fetch_stock_price_history

router = APIRouter(prefix="/api/stock")


@router.get("/{ticker}")
def get_stock_detail(ticker: str) -> Dict[str, Any]:
    """티커 기준 주식 상세 정보 반환."""
    try:
        return fetch_stock_detail(ticker.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"주식 데이터 조회 실패: {e}")


@router.get("/{ticker}/price-history")
def get_stock_price_history(ticker: str, days: int = 30) -> Dict[str, Any]:
    """주식 가격 히스토리 (차트용)."""
    data = fetch_stock_price_history(ticker.upper(), days)
    if not data["timestamps"]:
        raise HTTPException(status_code=503, detail="가격 데이터 조회 실패")
    return data


@router.get("")
def get_earnings_calendar() -> Dict[str, Any]:
    """보유 주식 어닝 캘린더."""
    with Session(engine) as db:
        holdings = db.query(StockHolding).filter(StockHolding.is_active == True).all()

    if not holdings:
        return {"earnings": []}

    tickers = [h.ticker for h in holdings]
    earnings = fetch_earnings_calendar(tickers)
    return {"earnings": earnings}
