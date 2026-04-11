"""분석 데이터 API 라우터."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from scheduler import get_portfolio_cache
from services import analyzer

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


@router.get("/beta")
def get_portfolio_beta() -> Dict[str, Any]:
    """포트폴리오 베타 (CoinGecko 기반, 다소 느림)."""
    cache = get_portfolio_cache()
    assets = cache.get("assets", []) if cache else []
    beta = analyzer.calculate_beta(assets)
    return {"beta": round(beta, 3) if beta is not None else None}


@router.get("/correlation")
def get_correlation_matrix() -> Dict[str, Any]:
    """보유 코인 간 상관관계 매트릭스 (CoinGecko 기반, 다소 느림)."""
    cache = get_portfolio_cache()
    assets = cache.get("assets", []) if cache else []
    result = analyzer.calculate_correlation_matrix(assets)
    return result if result else {"tickers": [], "matrix": []}
