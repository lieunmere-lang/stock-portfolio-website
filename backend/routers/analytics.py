"""분석 데이터 API 라우터."""
from datetime import datetime
from typing import Any, Dict, List, Optional

import requests
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from scheduler import get_portfolio_cache
from services import analyzer
from services.stock import get_usd_krw

router = APIRouter(prefix="/api/analytics")


@router.get("/summary")
def get_analytics_summary(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """기간별 수익률, 리스크 지표, 상위 5 종목, 분산도 반환."""
    cache = get_portfolio_cache()
    current_value = cache.get("total_value", 0) if cache else 0
    assets = cache.get("assets", []) if cache else []

    period_returns = analyzer.get_period_returns(db, current_value)
    mdd = analyzer.calculate_mdd(db)
    vol_sharpe = analyzer.calculate_volatility_and_sharpe(db)
    hhi = analyzer.calculate_hhi(assets)
    top5 = analyzer.get_top5_contributors(assets)

    return {
        "period_returns": period_returns,
        "risk_metrics": {
            "mdd": mdd,
            "volatility": vol_sharpe.get("volatility"),
            "sharpe": vol_sharpe.get("sharpe"),
            "hhi": round(hhi, 1),
        },
        "top5_contributors": top5,
        "diversification": {
            "asset_count": len(assets),
            "asset_types": list({a.get("asset_type", "crypto") for a in assets}),
        },
    }


@router.get("/history")
def get_analytics_history(
    days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """누적 수익률 차트용 히스토리 데이터."""
    return analyzer.get_history(db, days=days)



_fng_cache: Dict[str, Any] = {}


@router.get("/market")
def get_market_indicators() -> Dict[str, Any]:
    """공포탐욕지수 + USD/KRW 환율."""
    global _fng_cache

    # 공포탐욕지수 (10분 캐시)
    fng = None
    now = datetime.utcnow()
    if _fng_cache.get("data") and _fng_cache.get("fetched_at"):
        if (now - _fng_cache["fetched_at"]).total_seconds() < 600:
            fng = _fng_cache["data"]

    if not fng:
        try:
            res = requests.get("https://api.alternative.me/fng/", timeout=5)
            res.raise_for_status()
            d = res.json()["data"][0]
            fng = {"value": int(d["value"]), "label": d["value_classification"]}
            _fng_cache = {"data": fng, "fetched_at": now}
        except Exception:
            fng = None

    # USD/KRW 환율
    usd_krw = get_usd_krw()

    return {
        "fear_greed": fng,
        "usd_krw": round(usd_krw, 2) if usd_krw else None,
    }


@router.get("/correlation")
def get_correlation_matrix() -> Dict[str, Any]:
    """보유 코인 간 상관관계 매트릭스 (CoinGecko 기반, 다소 느림)."""
    cache = get_portfolio_cache()
    assets = cache.get("assets", []) if cache else []
    result = analyzer.calculate_correlation_matrix(assets)
    return result if result else {"tickers": [], "matrix": []}
