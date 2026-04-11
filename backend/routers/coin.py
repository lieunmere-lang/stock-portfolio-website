"""코인 상세 정보 라우터 — CoinGecko API 기반"""
from typing import Any, Dict, Optional

import requests
from fastapi import APIRouter, HTTPException

from services.analyzer import COINGECKO_BASE, COINGECKO_TIMEOUT, UPBIT_TO_COINGECKO
from services.upbit import fetch_upbit_candles

router = APIRouter(prefix="/api/coin")

GLOBAL_CACHE: Optional[Dict[str, Any]] = None


def _fetch_global() -> Dict[str, float]:
    """CoinGecko 글로벌 시장 점유율(도미넌스) 조회. {코인id: 점유율%}"""
    global GLOBAL_CACHE
    try:
        res = requests.get(f"{COINGECKO_BASE}/global", timeout=COINGECKO_TIMEOUT)
        res.raise_for_status()
        GLOBAL_CACHE = res.json().get("data", {}).get("market_cap_percentage", {})
        return GLOBAL_CACHE
    except Exception:
        return GLOBAL_CACHE or {}


@router.get("/{ticker}")
def get_coin_detail(ticker: str) -> Dict[str, Any]:
    """티커 기준 코인 상세 정보 반환 (CoinGecko)."""
    cg_id = UPBIT_TO_COINGECKO.get(ticker)
    if not cg_id:
        raise HTTPException(status_code=404, detail=f"{ticker}에 대한 CoinGecko 매핑 없음")

    try:
        res = requests.get(
            f"{COINGECKO_BASE}/coins/{cg_id}",
            params={
                "localization": "false",
                "tickers": "false",
                "community_data": "false",
                "developer_data": "false",
                "sparkline": "false",
            },
            timeout=15,
        )
        res.raise_for_status()
        data = res.json()
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"CoinGecko 조회 실패: {e}")

    md = data.get("market_data", {})
    links = data.get("links", {})

    # 도미넌스
    dominance_map = _fetch_global()
    symbol_lower = data.get("symbol", "").lower()
    dominance = dominance_map.get(symbol_lower)

    # 52주 고/저: ath/atl를 직접 사용하거나 1년 변동에서 추산
    # CoinGecko v3 free tier에는 high_52_week 필드 없음 → 최근 365일 데이터로 계산
    high_52w = md.get("high_52_week", {}).get("krw") if md.get("high_52_week") else None
    low_52w  = md.get("low_52_week", {}).get("krw")  if md.get("low_52_week")  else None

    homepage = None
    homepages = links.get("homepage") or []
    for h in homepages:
        if h:
            homepage = h
            break

    whitepaper = links.get("whitepaper") or None
    if not whitepaper:
        whitepaper = None

    return {
        "id": cg_id,
        "name": data.get("name"),
        "symbol": data.get("symbol", "").upper(),
        "image": (data.get("image") or {}).get("large"),
        "current_price_krw": (md.get("current_price") or {}).get("krw"),
        "price_change_24h_pct": md.get("price_change_percentage_24h"),
        "price_change_7d_pct":  md.get("price_change_percentage_7d"),
        "price_change_30d_pct": md.get("price_change_percentage_30d"),
        "price_change_1y_pct":  md.get("price_change_percentage_1y"),
        "market_cap_krw":    (md.get("market_cap") or {}).get("krw"),
        "market_cap_rank":   md.get("market_cap_rank"),
        "volume_24h_krw":    (md.get("total_volume") or {}).get("krw"),
        "high_24h_krw":      (md.get("high_24h") or {}).get("krw"),
        "low_24h_krw":       (md.get("low_24h") or {}).get("krw"),
        "high_52w_krw":      high_52w,
        "low_52w_krw":       low_52w,
        "ath_krw":           (md.get("ath") or {}).get("krw"),
        "ath_date":          (md.get("ath_date") or {}).get("krw"),
        "circulating_supply": md.get("circulating_supply"),
        "total_supply":      md.get("total_supply"),
        "max_supply":        md.get("max_supply"),
        "dominance_pct":     dominance,
        "homepage":  homepage,
        "whitepaper": whitepaper if whitepaper else None,
        "description_en": (data.get("description") or {}).get("en", "")[:800] or None,
    }


@router.get("/{ticker}/price-history")
def get_coin_price_history(ticker: str, days: int = 30) -> Dict[str, Any]:
    """업비트 일봉 캔들 기반 가격 히스토리 반환 (차트용)."""
    # ETH2 → ETH 캔들 사용
    candle_ticker = ticker
    if ticker == "KRW-ETH2":
        candle_ticker = "KRW-ETH"

    price_map = fetch_upbit_candles(candle_ticker, count=days)
    if not price_map:
        raise HTTPException(status_code=503, detail="가격 데이터 조회 실패")

    sorted_dates = sorted(price_map.keys())[-days:]
    return {
        "ticker": ticker,
        "timestamps": sorted_dates,
        "prices": [price_map[d] for d in sorted_dates],
    }
