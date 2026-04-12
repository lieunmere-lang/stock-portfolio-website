"""미국 주식 데이터 서비스 — yfinance 기반."""
import time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import yfinance as yf

# ── 메모리 캐시 ──────────────────────────────────────────────────────────────
_detail_cache: Dict[str, Dict[str, Any]] = {}   # ticker -> {data, fetched_at}
_earnings_cache: Dict[str, Any] = {}             # {"data": [...], "fetched_at": datetime}
_usd_krw_cache: Dict[str, Any] = {"rate": None, "fetched_at": None}

DETAIL_TTL = 900        # 15분
EARNINGS_TTL = 21600     # 6시간
FX_TTL = 3600            # 1시간


def get_usd_krw() -> Optional[float]:
    """USD/KRW 환율 조회 (캐시 1시간)."""
    now = datetime.utcnow()
    cached = _usd_krw_cache
    if cached["rate"] and cached["fetched_at"]:
        if (now - cached["fetched_at"]).total_seconds() < FX_TTL:
            return cached["rate"]
    try:
        ticker = yf.Ticker("USDKRW=X")
        hist = ticker.history(period="1d")
        if hist.empty:
            return cached["rate"]  # fallback
        rate = float(hist["Close"].iloc[-1])
        _usd_krw_cache["rate"] = rate
        _usd_krw_cache["fetched_at"] = now
        return rate
    except Exception:
        return cached["rate"]


def fetch_stock_detail(ticker: str) -> Dict[str, Any]:
    """종목 상세 정보 조회 (캐시 15분)."""
    now = datetime.utcnow()
    cached = _detail_cache.get(ticker)
    if cached and (now - cached["fetched_at"]).total_seconds() < DETAIL_TTL:
        return cached["data"]

    t = yf.Ticker(ticker)
    info = t.info
    if not info or not info.get("symbol"):
        raise ValueError(f"Unknown ticker: {ticker}")

    usd_krw = get_usd_krw()

    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
    price_change = None
    price_change_pct = None
    if current_price and previous_close and previous_close > 0:
        price_change = current_price - previous_close
        price_change_pct = (price_change / previous_close) * 100

    data = {
        "symbol": info.get("symbol"),
        "name": info.get("shortName") or info.get("longName"),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange"),
        "current_price": current_price,
        "previous_close": previous_close,
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "post_market_price": info.get("postMarketPrice"),
        "post_market_change_pct": info.get("postMarketChangePercent"),
        "current_price_krw": current_price * usd_krw if current_price and usd_krw else None,
        "usd_krw": usd_krw,
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "dividend_yield": info.get("dividendYield"),
        "dividend_rate": info.get("dividendRate"),
        "ex_dividend_date": _ts_to_str(info.get("exDividendDate")),
        "market_cap": info.get("marketCap"),
        "volume": info.get("volume"),
        "average_volume": info.get("averageVolume"),
        "day_low": info.get("dayLow"),
        "day_high": info.get("dayHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
        "target_mean_price": info.get("targetMeanPrice"),
        "target_low_price": info.get("targetLowPrice"),
        "target_high_price": info.get("targetHighPrice"),
        "recommendation_key": info.get("recommendationKey"),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),
        "earnings_dates": _get_next_earnings(t),
        "website": info.get("website"),
        "logo_url": info.get("logo_url"),
    }

    _detail_cache[ticker] = {"data": data, "fetched_at": now}
    return data


def fetch_stock_price_history(ticker: str, days: int = 30) -> Dict[str, Any]:
    """주식 가격 히스토리 (차트용)."""
    period_map = {30: "1mo", 90: "3mo", 180: "6mo", 365: "1y"}
    period = period_map.get(days, "1mo")

    t = yf.Ticker(ticker)
    hist = t.history(period=period)
    if hist.empty:
        return {"ticker": ticker, "timestamps": [], "prices": []}

    timestamps = [d.strftime("%Y-%m-%d") for d in hist.index]
    prices = [round(float(p), 2) for p in hist["Close"]]

    return {"ticker": ticker, "timestamps": timestamps, "prices": prices}


def fetch_earnings_calendar(tickers: List[str]) -> List[Dict[str, Any]]:
    """보유 주식의 다가오는 어닝 날짜 목록 (캐시 6시간)."""
    now = datetime.utcnow()
    cached = _earnings_cache
    if cached.get("data") and cached.get("fetched_at"):
        if (now - cached["fetched_at"]).total_seconds() < EARNINGS_TTL:
            return cached["data"]

    results = []
    cutoff = now + timedelta(days=90)

    for ticker in tickers:
        try:
            t = yf.Ticker(ticker)
            info = t.info
            name = info.get("shortName") or ticker
            dates = _get_next_earnings(t)
            if dates:
                for date_str in dates:
                    dt = datetime.strptime(date_str, "%Y-%m-%d")
                    if now <= dt <= cutoff:
                        days_until = (dt - now).days
                        results.append({
                            "ticker": ticker,
                            "name": name,
                            "earnings_date": date_str,
                            "days_until": days_until,
                        })
            time.sleep(0.1)
        except Exception:
            continue

    results.sort(key=lambda x: x["earnings_date"])
    _earnings_cache["data"] = results
    _earnings_cache["fetched_at"] = now
    return results


def _get_next_earnings(t: yf.Ticker) -> List[str]:
    """Ticker 객체에서 다가오는 어닝 날짜 추출."""
    try:
        cal = t.calendar
        if cal is None:
            return []
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date", [])
            if isinstance(dates, list):
                return [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in dates]
        else:
            if "Earnings Date" in cal.columns:
                return [d.strftime("%Y-%m-%d") for d in cal["Earnings Date"].dropna()]
            elif "Earnings Date" in cal.index:
                vals = cal.loc["Earnings Date"]
                return [v.strftime("%Y-%m-%d") if hasattr(v, "strftime") else str(v) for v in vals if v]
    except Exception:
        pass
    return []


def _ts_to_str(ts) -> Optional[str]:
    """Unix timestamp → YYYY-MM-DD 문자열."""
    if ts is None:
        return None
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d")
    except Exception:
        return None
