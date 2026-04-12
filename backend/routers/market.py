"""시장 상황판 API 라우터."""
from typing import Any, Dict

from fastapi import APIRouter, Query

from services.market import fetch_heatmap_data, fetch_market_indicators

router = APIRouter(prefix="/api/market")


@router.get("/heatmap")
def get_heatmap(period: str = Query(default="1d", pattern="^(1d|1w|1mo|ytd)$")) -> Dict[str, Any]:
    """히트맵 데이터 반환.

    period: 1d (당일), 1w (1주), 1mo (1개월), ytd (연초대비)
    """
    return fetch_heatmap_data(period)


@router.get("/indicators")
def get_indicators() -> Dict[str, Any]:
    """시장 지표 위젯 데이터 반환."""
    return fetch_market_indicators()
