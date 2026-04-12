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
    """보유 종목(코인+주식) 간 상관관계 매트릭스."""
    cache = get_portfolio_cache()
    assets = cache.get("assets", []) if cache else []
    result = analyzer.calculate_correlation_matrix(assets)
    return result if result else {"tickers": [], "matrix": []}


@router.get("/fx-impact")
def get_fx_impact() -> Dict[str, Any]:
    """미국 주식의 환율 영향 분석 — USD 수익률 vs KRW 환산 수익률 분리."""
    cache = get_portfolio_cache()
    assets = cache.get("assets", []) if cache else []
    usd_krw = get_usd_krw()

    stock_assets = [a for a in assets if a.get("asset_type") == "stock"]
    if not stock_assets or not usd_krw:
        return {"items": [], "summary": None}

    items = []
    total_investment_krw = 0
    total_value_krw = 0
    total_value_usd = 0
    total_investment_usd = 0

    for a in stock_assets:
        avg_usd = a.get("avg_price_usd", 0) or 0
        cur_usd = a.get("current_price_usd", 0) or 0
        qty = a.get("quantity", 0)

        if avg_usd <= 0 or cur_usd <= 0 or qty <= 0:
            continue

        # USD 기준 수익률
        usd_return = (cur_usd - avg_usd) / avg_usd * 100

        # KRW 환산 수익률 (실제 포트폴리오에 반영된 수익률)
        avg_krw = a.get("avg_price", 0)
        cur_krw = a.get("current_price", 0)
        krw_return = (cur_krw - avg_krw) / avg_krw * 100 if avg_krw > 0 else 0

        # 환율 영향 = KRW 수익률 - USD 수익률
        fx_impact = krw_return - usd_return

        investment_usd = avg_usd * qty
        value_usd = cur_usd * qty
        investment_krw = a.get("avg_price", 0) * qty
        value_krw = a.get("total_value", 0)

        total_investment_usd += investment_usd
        total_value_usd += value_usd
        total_investment_krw += investment_krw
        total_value_krw += value_krw

        items.append({
            "ticker": a["ticker"],
            "name": a["name"],
            "usd_return": round(usd_return, 2),
            "krw_return": round(krw_return, 2),
            "fx_impact": round(fx_impact, 2),
            "investment_usd": round(investment_usd, 2),
            "value_usd": round(value_usd, 2),
            "pnl_usd": round(value_usd - investment_usd, 2),
        })

    # 전체 요약
    summary = None
    if total_investment_usd > 0 and total_investment_krw > 0:
        total_usd_return = (total_value_usd - total_investment_usd) / total_investment_usd * 100
        total_krw_return = (total_value_krw - total_investment_krw) / total_investment_krw * 100
        summary = {
            "total_usd_return": round(total_usd_return, 2),
            "total_krw_return": round(total_krw_return, 2),
            "fx_impact": round(total_krw_return - total_usd_return, 2),
            "usd_krw": round(usd_krw, 2),
        }

    return {"items": items, "summary": summary}
