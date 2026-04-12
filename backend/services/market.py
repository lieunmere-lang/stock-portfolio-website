"""시장 상황판 데이터 서비스."""
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
import yfinance as yf

# ── 캐시 ──────────────────────────────────────────────────────────────────────
_sp500_cache: Dict[str, Any] = {}          # {"data": [...], "fetched_at": datetime}
_heatmap_cache: Dict[str, Any] = {}        # {period: {"data": {...}, "fetched_at": datetime}}
_indicators_cache: Dict[str, Any] = {}     # {"data": {...}, "fetched_at": datetime}

SP500_TTL = 86400 * 7    # 7일 (종목 구성은 드물게 변경)
HEATMAP_TTL = 900         # 15분
INDICATORS_TTL = 600      # 10분


def get_sp500_list() -> List[Dict[str, str]]:
    """S&P500 종목 목록 반환. [{ticker, name, sector}, ...]

    Wikipedia 테이블을 파싱하여 캐시(7일). 실패 시 빈 리스트 반환.
    """
    now = datetime.utcnow()
    cached = _sp500_cache
    if cached.get("data") and cached.get("fetched_at"):
        if (now - cached["fetched_at"]).total_seconds() < SP500_TTL:
            return cached["data"]

    try:
        import pandas as pd
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        tables = pd.read_html(url)
        df = tables[0]
        result = []
        for _, row in df.iterrows():
            ticker = str(row["Symbol"]).replace(".", "-")  # BRK.B → BRK-B (yfinance 형식)
            result.append({
                "ticker": ticker,
                "name": str(row["Security"]),
                "sector": str(row["GICS Sector"]),
            })
        _sp500_cache["data"] = result
        _sp500_cache["fetched_at"] = now
        print(f"[Market] S&P500 목록 로드 완료: {len(result)}개 종목")
        return result
    except Exception as e:
        print(f"[Market] S&P500 목록 로드 실패: {e}")
        return _sp500_cache.get("data", [])
