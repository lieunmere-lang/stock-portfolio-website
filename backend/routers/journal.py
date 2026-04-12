"""매매일지 API 라우터."""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services.journal import (
    add_manual_trade,
    delete_trade,
    get_trade_summary,
    get_trades,
    sync_upbit_trades,
)

router = APIRouter(prefix="/api/journal")


class ManualTradeRequest(BaseModel):
    ticker: str
    name: str = ""
    side: str  # "buy" | "sell"
    price: float
    quantity: float
    fee: float = 0
    asset_type: str = "crypto"
    traded_at: str = ""
    memo: str = ""


@router.get("/trades")
def api_get_trades(
    ticker: Optional[str] = Query(default=None),
    side: Optional[str] = Query(default=None),
    days: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """매매 기록 조회."""
    return get_trades(db, ticker=ticker, side=side, days=days, limit=limit, offset=offset)


@router.get("/summary")
def api_get_summary(
    ticker: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """종목별 매매 요약."""
    return get_trade_summary(db, ticker=ticker)


@router.post("/sync")
def api_sync_upbit(
    days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """업비트 거래내역 자동 가져오기."""
    return sync_upbit_trades(db, days=days)


@router.post("/trades")
def api_add_trade(
    req: ManualTradeRequest,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """수동 매매 기록 추가."""
    return add_manual_trade(db, req.model_dump())


@router.delete("/trades/{trade_id}")
def api_delete_trade(
    trade_id: int,
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """매매 기록 삭제."""
    ok = delete_trade(db, trade_id)
    if not ok:
        return {"status": "not_found"}
    return {"status": "deleted"}
