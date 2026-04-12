"""시장 상황판 데이터 서비스."""
import json as _json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests
import yfinance as yf

_CACHE_DIR = Path(__file__).resolve().parent.parent / ".cache"
_MCAP_FILE = _CACHE_DIR / "sp500_market_caps.json"

# ── 캐시 ──────────────────────────────────────────────────────────────────────
_sp500_cache: Dict[str, Any] = {}          # {"data": [...], "fetched_at": datetime}
_heatmap_cache: Dict[str, Any] = {}        # {period: {"data": {...}, "fetched_at": datetime}}
_indicators_cache: Dict[str, Any] = {}     # {"data": {...}, "fetched_at": datetime}

SP500_TTL = 86400 * 7    # 7일 (종목 구성은 드물게 변경)
HEATMAP_TTL = 900         # 15분
INDICATORS_TTL = 600      # 10분
MCAP_TTL = 600            # 10분

_mcap_cache: Dict[str, Any] = {}  # {"data": {ticker: mcap}, "fetched_at": datetime}


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
        import io
        url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=15)
        resp.raise_for_status()
        tables = pd.read_html(io.StringIO(resp.text))
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


# ── 기간 변환 ─────────────────────────────────────────────────────────────────

def _period_to_yf(period: str) -> str:
    """프론트엔드 period 문자열을 yfinance period로 변환."""
    mapping = {
        "1d": "2d",
        "1w": "6d",
        "1mo": "1mo",
        "ytd": "ytd",
    }
    return mapping.get(period, "2d")


# ── 히트맵 데이터 수집 ────────────────────────────────────────────────────────

def fetch_heatmap_data(period: str = "1d") -> Dict[str, List[Dict]]:
    """히트맵 데이터 반환. {"stocks": [...], "coins": [...], "commodities": [...]}

    _heatmap_cache에 period별로 캐시(15분 TTL).
    """
    now = datetime.utcnow()
    cached = _heatmap_cache.get(period)
    if cached and cached.get("data") and cached.get("fetched_at"):
        if (now - cached["fetched_at"]).total_seconds() < HEATMAP_TTL:
            return cached["data"]

    stocks = _fetch_stock_heatmap(period)
    coins = _fetch_coin_heatmap(period)
    commodities = _fetch_commodity_heatmap(period)

    result = {"stocks": stocks, "coins": coins, "commodities": commodities}
    _heatmap_cache[period] = {"data": result, "fetched_at": now}
    return result


STOCKS_PER_SECTOR = 5  # 섹터별 상위 N개 종목만 표시


def _fetch_stock_heatmap(period: str) -> List[Dict]:
    """S&P500에서 섹터별 시총 상위 종목의 히트맵 데이터 수집."""
    yf_period = _period_to_yf(period)
    sp500 = get_sp500_list()
    if not sp500:
        return []

    all_tickers = [item["ticker"] for item in sp500]
    ticker_meta = {item["ticker"]: item for item in sp500}

    # 시가총액 캐시에서 섹터별 상위 N개 선별
    market_caps = _get_sp500_market_caps(all_tickers)

    sector_groups: Dict[str, List[Dict]] = {}
    for item in sp500:
        sector = item["sector"]
        if sector not in sector_groups:
            sector_groups[sector] = []
        sector_groups[sector].append({
            **item,
            "market_cap": market_caps.get(item["ticker"], 0),
        })

    # 각 섹터에서 시총 상위 N개만 선택
    selected_tickers = []
    for sector, items in sector_groups.items():
        items.sort(key=lambda x: x["market_cap"], reverse=True)
        for item in items[:STOCKS_PER_SECTOR]:
            selected_tickers.append(item["ticker"])

    if not selected_tickers:
        return []

    try:
        data = yf.download(
            selected_tickers,
            period=yf_period,
            group_by="ticker",
            threads=True,
            progress=False,
        )
    except Exception as e:
        print(f"[Market] 주식 히트맵 다운로드 실패: {e}")
        return []

    result = []
    multi = len(selected_tickers) > 1
    for ticker in selected_tickers:
        try:
            ticker_data = data[ticker] if multi else data
            if ticker_data is None or ticker_data.empty:
                continue
            closes = ticker_data["Close"].dropna()
            if closes.empty:
                continue

            if len(closes) >= 2:
                first_close = float(closes.iloc[0])
                last_close = float(closes.iloc[-1])
            else:
                opens = ticker_data["Open"].dropna()
                first_close = float(opens.iloc[0]) if not opens.empty else float(closes.iloc[0])
                last_close = float(closes.iloc[0])
            if first_close == 0:
                continue
            change_pct = (last_close - first_close) / first_close * 100
            meta = ticker_meta.get(ticker, {})
            result.append({
                "ticker": ticker,
                "name": meta.get("name", ticker),
                "sector": meta.get("sector", ""),
                "market_cap": market_caps.get(ticker, last_close * 1e6),
                "change_pct": round(change_pct, 2),
            })
        except Exception as e:
            print(f"[Market] {ticker} 히트맵 처리 오류: {e}")
            continue

    return result


def _get_sp500_market_caps(tickers: List[str]) -> Dict[str, float]:
    """S&P500 종목 실제 시가총액 조회 (파일 캐시 24시간).

    파일 캐시(.cache/sp500_market_caps.json)를 먼저 확인.
    없거나 오래되면 yfinance로 일괄 조회 후 파일에 저장.
    """
    # 1) 메모리 캐시 확인
    now = datetime.utcnow()
    cached = _mcap_cache
    if cached.get("data") and cached.get("fetched_at"):
        if (now - cached["fetched_at"]).total_seconds() < MCAP_TTL:
            return cached["data"]

    # 2) 파일 캐시 확인
    stale_data = None
    if _MCAP_FILE.exists():
        try:
            file_data = _json.loads(_MCAP_FILE.read_text())
            fetched_at = datetime.fromisoformat(file_data["fetched_at"])
            stale_data = file_data["data"]  # 만료되더라도 fallback용 보관
            if (now - fetched_at).total_seconds() < MCAP_TTL:
                _mcap_cache["data"] = file_data["data"]
                _mcap_cache["fetched_at"] = fetched_at
                return file_data["data"]
        except Exception as e:
            print(f"[Market] 파일 캐시 로드 실패: {e}")

    # 3) yfinance에서 일괄 조회 (동기화 중에는 이전값 반환)
    # 히트맵 API 요청 시에는 기존 캐시 반환, 스케줄러가 백그라운드에서 갱신
    if stale_data:
        _mcap_cache["data"] = stale_data
        _mcap_cache["fetched_at"] = now  # 임시로 TTL 리셋 (스케줄러가 곧 갱신)
        return stale_data
    print("[Market] S&P500 시가총액 일괄 조회 시작...")
    mcap_dict: Dict[str, float] = {}
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            tickers_obj = yf.Tickers(" ".join(batch))
            for ticker in batch:
                try:
                    mcap = getattr(tickers_obj.tickers[ticker].fast_info, "market_cap", None) or 0
                    mcap_dict[ticker] = float(mcap)
                except Exception:
                    mcap_dict[ticker] = 0
        except Exception as e:
            print(f"[Market] 시가총액 배치 {i} 실패: {e}")
            for ticker in batch:
                mcap_dict.setdefault(ticker, 0)

    # 메모리 + 파일 캐시 저장
    _mcap_cache["data"] = mcap_dict
    _mcap_cache["fetched_at"] = now
    try:
        _CACHE_DIR.mkdir(parents=True, exist_ok=True)
        _MCAP_FILE.write_text(_json.dumps({
            "data": mcap_dict,
            "fetched_at": now.isoformat(),
        }))
    except Exception as e:
        print(f"[Market] 파일 캐시 저장 실패: {e}")

    print(f"[Market] 시가총액 조회 완료: {len(mcap_dict)}개")
    return mcap_dict


def _fetch_coin_heatmap(period: str) -> List[Dict]:
    """CoinGecko에서 상위 5개 코인 히트맵 데이터 수집."""
    period_field_map = {
        "1d": "price_change_percentage_24h",
        "1w": "price_change_percentage_7d_in_currency",
        "1mo": "price_change_percentage_30d_in_currency",
        "ytd": "price_change_percentage_24h",  # ytd는 24h로 대체
    }
    change_field = period_field_map.get(period, "price_change_percentage_24h")

    url = "https://api.coingecko.com/api/v3/coins/markets"
    params = {
        "vs_currency": "usd",
        "order": "market_cap_desc",
        "per_page": 5,
        "page": 1,
        "sparkline": "false",
        "price_change_percentage": "1h,24h,7d,30d",
    }

    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        coins = resp.json()
    except Exception as e:
        print(f"[Market] CoinGecko 코인 히트맵 조회 실패: {e}")
        return []

    result = []
    for coin in coins:
        try:
            change_pct = coin.get(change_field) or 0.0
            result.append({
                "ticker": str(coin.get("symbol", "")).upper(),
                "name": coin.get("name", ""),
                "market_cap": coin.get("market_cap", 0),
                "change_pct": round(float(change_pct), 2),
            })
        except Exception as e:
            print(f"[Market] 코인 히트맵 처리 오류: {e}")
            continue

    return result


def _fetch_commodity_heatmap(period: str) -> List[Dict]:
    """금, 은, WTI 원자재 히트맵 데이터 수집."""
    yf_period = _period_to_yf(period)
    commodities = [
        ("GC=F", "금", "GOLD"),
        ("SI=F", "은", "SILVER"),
        ("CL=F", "WTI", "WTI"),
    ]

    result = []
    for yf_ticker, name, display_ticker in commodities:
        try:
            hist = yf.Ticker(yf_ticker).history(period=yf_period)
            if hist is None or hist.empty:
                continue
            closes = hist["Close"].dropna()
            if closes.empty:
                continue

            if len(closes) >= 2:
                # 2일 이상 데이터가 있으면 첫날 대비 마지막날 변동률
                first_close = float(closes.iloc[0])
                last_close = float(closes.iloc[-1])
            else:
                # 1일치만 있으면 (주말/휴일) 시가 대비 종가 변동률
                opens = hist["Open"].dropna()
                first_close = float(opens.iloc[0]) if not opens.empty else float(closes.iloc[0])
                last_close = float(closes.iloc[0])

            if first_close == 0:
                continue
            change_pct = (last_close - first_close) / first_close * 100
            result.append({
                "ticker": display_ticker,
                "name": name,
                "change_pct": round(change_pct, 2),
            })
        except Exception as e:
            print(f"[Market] {yf_ticker} 원자재 히트맵 처리 오류: {e}")
            continue

    return result


# ── 위젯 지표 수집 ────────────────────────────────────────────────────────────

def fetch_market_indicators() -> Dict[str, Any]:
    """8개 위젯 카드용 시장 지표 반환. _indicators_cache에 10분 TTL 캐시."""
    now = datetime.utcnow()
    cached = _indicators_cache
    if cached.get("data") and cached.get("fetched_at"):
        if (now - cached["fetched_at"]).total_seconds() < INDICATORS_TTL:
            return cached["data"]

    result: Dict[str, Any] = {}
    result["fear_greed"] = _fetch_fear_greed()
    result["usd_krw"] = _fetch_yf_indicator("USDKRW=X", "USD/KRW")
    result["jpy_krw"] = _fetch_yf_indicator("JPYKRW=X", "JPY/KRW")
    result["vix"] = _fetch_yf_indicator("^VIX", "VIX")
    result["dxy"] = _fetch_yf_indicator("DX-Y.NYB", "DXY")
    result["us10y"] = _fetch_yf_indicator("^TNX", "US 10Y")
    result["btc_dominance"] = _fetch_btc_dominance()
    result["kimchi_premium"] = _fetch_kimchi_premium(result.get("usd_krw", {}).get("value"))

    _indicators_cache["data"] = result
    _indicators_cache["fetched_at"] = now
    return result


def _fetch_yf_indicator(yf_ticker: str, label: str) -> Dict[str, Any]:
    """yfinance에서 단일 지표 데이터 수집."""
    try:
        hist = yf.Ticker(yf_ticker).history(period="10d")
        if hist is None or len(hist) < 2:
            return {"value": None, "change_pct": None, "sparkline": []}
        closes = hist["Close"].dropna().tolist()
        if len(closes) < 2:
            return {"value": None, "change_pct": None, "sparkline": []}
        current = closes[-1]
        prev = closes[-2]
        change_pct = (current - prev) / prev * 100 if prev != 0 else 0.0
        sparkline = [round(v, 4) for v in closes[-7:]]
        return {
            "value": round(current, 2),
            "change_pct": round(change_pct, 2),
            "sparkline": sparkline,
        }
    except Exception as e:
        print(f"[Market] {label} ({yf_ticker}) 지표 조회 실패: {e}")
        return {"value": None, "change_pct": None, "sparkline": []}


def _fetch_fear_greed() -> Dict[str, Any]:
    """Alternative.me Fear & Greed Index 조회."""
    try:
        resp = requests.get("https://api.alternative.me/fng/?limit=7", timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if not data:
            return {"value": None, "label": None, "sparkline": []}
        current = data[0]
        value = int(current["value"])
        label = current.get("value_classification", "")
        sparkline = [int(item["value"]) for item in reversed(data)]
        return {"value": value, "label": label, "sparkline": sparkline}
    except Exception as e:
        print(f"[Market] Fear & Greed Index 조회 실패: {e}")
        return {"value": None, "label": None, "sparkline": []}


def _fetch_btc_dominance() -> Dict[str, Any]:
    """CoinGecko에서 BTC 도미넌스 조회."""
    try:
        resp = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", {})
        btc_dom = data.get("market_cap_percentage", {}).get("btc")
        if btc_dom is None:
            return {"value": None, "change_pct": None, "sparkline": []}
        btc_dom = round(float(btc_dom), 1)
        return {"value": btc_dom, "change_pct": None, "sparkline": [btc_dom]}
    except Exception as e:
        print(f"[Market] BTC 도미넌스 조회 실패: {e}")
        return {"value": None, "change_pct": None, "sparkline": []}


def _fetch_kimchi_premium(usd_krw_rate: Optional[float] = None) -> Dict[str, Any]:
    """김치 프리미엄 계산 (업비트 BTC/KRW vs CoinGecko BTC/USD)."""
    try:
        # 업비트 BTC/KRW
        upbit_resp = requests.get(
            "https://api.upbit.com/v1/ticker?markets=KRW-BTC", timeout=10
        )
        upbit_resp.raise_for_status()
        upbit_btc_krw = float(upbit_resp.json()[0]["trade_price"])

        # CoinGecko BTC/USD
        cg_resp = requests.get(
            "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=usd",
            timeout=10,
        )
        cg_resp.raise_for_status()
        btc_usd = float(cg_resp.json()["bitcoin"]["usd"])

        # USD/KRW 환율
        usd_krw = usd_krw_rate
        if usd_krw is None:
            from services.stock import get_usd_krw
            usd_krw = get_usd_krw()

        if not usd_krw or usd_krw == 0:
            return {"value": None, "change_pct": None, "sparkline": []}

        premium = ((upbit_btc_krw - btc_usd * usd_krw) / (btc_usd * usd_krw)) * 100
        premium = round(premium, 2)
        return {"value": premium, "change_pct": None, "sparkline": [premium]}
    except Exception as e:
        print(f"[Market] 김치 프리미엄 계산 실패: {e}")
        return {"value": None, "change_pct": None, "sparkline": []}
