"""시장 지표 수집 서비스 — 공포탐욕지수, VIX, BTC 도미넌스, 원/달러 환율"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MarketIndicators:
    fear_greed_index: Optional[int] = None
    fear_greed_label: Optional[str] = None
    vix: Optional[float] = None
    btc_dominance: Optional[float] = None
    usd_krw: Optional[float] = None


async def fetch_indicators() -> MarketIndicators:
    """모든 시장 지표를 한 번에 수집"""
    indicators = MarketIndicators()

    async with httpx.AsyncClient(timeout=10) as client:
        # 공포탐욕지수
        try:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            data = resp.json()["data"][0]
            indicators.fear_greed_index = int(data["value"])
            indicators.fear_greed_label = data["value_classification"]
        except Exception as e:
            logger.warning(f"Fear & Greed fetch failed: {e}")

        # BTC 도미넌스 (CoinGecko)
        try:
            resp = await client.get("https://api.coingecko.com/api/v3/global")
            data = resp.json()["data"]
            indicators.btc_dominance = round(data["market_cap_percentage"]["btc"], 1)
        except Exception as e:
            logger.warning(f"BTC dominance fetch failed: {e}")

        # VIX (Yahoo Finance)
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")
            if not hist.empty:
                indicators.vix = round(hist["Close"].iloc[-1], 2)
        except Exception as e:
            logger.warning(f"VIX fetch failed: {e}")

        # 원/달러 환율
        try:
            from services.stock import get_usd_krw
            indicators.usd_krw = get_usd_krw()
        except Exception as e:
            logger.warning(f"USD/KRW fetch failed: {e}")

    return indicators
