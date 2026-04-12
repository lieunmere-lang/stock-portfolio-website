# 시장 상황판 (Market Overview) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Finviz 스타일 S&P500 트리맵 히트맵 + 시장 지표 위젯 카드로 구성된 시장 상황판 페이지 구축

**Architecture:** 백엔드에 `services/market.py` (데이터 수집·캐싱) + `routers/market.py` (API 엔드포인트 2개) 추가. 프론트엔드에 `market.html` 페이지를 만들고 D3.js로 트리맵을 렌더링하며, 위젯 카드는 SVG 스파크라인과 함께 표시. 기존 사이드바의 "시장 상황판 준비중" 링크를 활성화.

**Tech Stack:** Python/FastAPI, yfinance, CoinGecko API, Alternative.me API, D3.js (CDN), 바닐라 JS, Bootstrap 5

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/services/market.py` | S&P500 종목 목록, 히트맵 데이터 수집, 위젯 지표 수집, 캐싱 |
| Create | `backend/routers/market.py` | `/api/market/heatmap`, `/api/market/indicators` 엔드포인트 |
| Modify | `backend/main.py:14-51` | market 라우터 import 및 등록 |
| Create | `frontend/market.html` | 시장 상황판 페이지 (히트맵 + 위젯) |
| Modify | `frontend/index.html:193` | 사이드바 "시장 상황판" 링크 활성화 |
| Modify | `frontend/news.html:202` | 사이드바 "시장 상황판" 링크 활성화 |
| Modify | `frontend/detail.html` | 사이드바 "시장 상황판" 링크 활성화 (존재하면) |

---

### Task 1: S&P500 종목 목록 데이터 서비스

**Files:**
- Create: `backend/services/market.py`

- [ ] **Step 1: S&P500 종목 목록 함수 작성**

Wikipedia에서 S&P500 종목 목록을 스크래핑하여 캐싱하는 함수를 작성한다. pandas의 `read_html`을 사용.

```python
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
```

- [ ] **Step 2: 서버 시작하여 import 확인**

Run: `cd backend && python -c "from services.market import get_sp500_list; print(len(get_sp500_list()))"`
Expected: `503` 또는 그와 비슷한 숫자 출력 (S&P500 종목 수)

- [ ] **Step 3: pandas를 requirements.txt에 추가 (없는 경우)**

`backend/requirements.txt`에 `pandas`가 없으면 추가. yfinance가 이미 pandas를 의존성으로 가져오지만 명시적으로 추가.

```
pandas
lxml
```

`lxml`은 `pd.read_html`이 HTML 파싱에 사용.

- [ ] **Step 4: 커밋**

```bash
git add backend/services/market.py backend/requirements.txt
git commit -m "feat(market): add S&P500 list fetcher with Wikipedia scraping"
```

---

### Task 2: 히트맵 데이터 수집 함수

**Files:**
- Modify: `backend/services/market.py`

- [ ] **Step 1: 히트맵 데이터 수집 함수 작성**

`backend/services/market.py`에 히트맵 데이터를 수집하는 함수를 추가한다. yfinance 배치 다운로드로 S&P500 전체 주가를 한 번에 가져오고, CoinGecko로 코인 데이터를 가져온다.

```python
def _period_to_yf(period: str) -> str:
    """프론트엔드 period 파라미터를 yfinance period로 변환."""
    mapping = {"1d": "2d", "1w": "6d", "1mo": "1mo", "ytd": "ytd"}
    return mapping.get(period, "2d")


def fetch_heatmap_data(period: str = "1d") -> Dict[str, Any]:
    """히트맵용 전체 데이터 수집. 캐시 15분.

    Returns: {"stocks": [...], "coins": [...], "commodities": [...]}
    """
    now = datetime.utcnow()
    cache_key = period
    cached = _heatmap_cache.get(cache_key)
    if cached and (now - cached["fetched_at"]).total_seconds() < HEATMAP_TTL:
        return cached["data"]

    stocks = _fetch_stock_heatmap(period)
    coins = _fetch_coin_heatmap(period)
    commodities = _fetch_commodity_heatmap(period)

    result = {"stocks": stocks, "coins": coins, "commodities": commodities}
    _heatmap_cache[cache_key] = {"data": result, "fetched_at": now}
    return result


def _fetch_stock_heatmap(period: str) -> List[Dict[str, Any]]:
    """S&P500 전체 종목의 등락률 + 시가총액 반환."""
    sp500 = get_sp500_list()
    if not sp500:
        return []

    tickers = [s["ticker"] for s in sp500]
    sector_map = {s["ticker"]: s["sector"] for s in sp500}
    name_map = {s["ticker"]: s["name"] for s in sp500}

    yf_period = _period_to_yf(period)

    try:
        # 배치 다운로드: 500종목을 한 번의 요청으로
        data = yf.download(tickers, period=yf_period, group_by="ticker", threads=True, progress=False)
        if data.empty:
            return []

        result = []
        for ticker in tickers:
            try:
                if len(tickers) == 1:
                    ticker_data = data
                else:
                    ticker_data = data[ticker]

                if ticker_data.empty or len(ticker_data) < 2:
                    continue

                close_first = float(ticker_data["Close"].iloc[0])
                close_last = float(ticker_data["Close"].iloc[-1])

                if close_first <= 0:
                    continue

                change_pct = ((close_last - close_first) / close_first) * 100

                # 시가총액은 yfinance info에서 별도로 가져오면 너무 느림
                # fast_info 사용
                try:
                    mcap = yf.Ticker(ticker).fast_info.get("marketCap", 0)
                except Exception:
                    mcap = 0

                result.append({
                    "ticker": ticker,
                    "name": name_map.get(ticker, ticker),
                    "sector": sector_map.get(ticker, "Unknown"),
                    "market_cap": mcap,
                    "change_pct": round(change_pct, 2),
                })
            except Exception:
                continue

        print(f"[Market] S&P500 히트맵 데이터: {len(result)}개 종목 (period={period})")
        return result
    except Exception as e:
        print(f"[Market] S&P500 다운로드 실패: {e}")
        return []


def _fetch_coin_heatmap(period: str) -> List[Dict[str, Any]]:
    """CoinGecko에서 시총 상위 5개 코인 데이터 반환."""
    days_map = {"1d": "1", "1w": "7", "1mo": "30", "ytd": "365"}
    days = days_map.get(period, "1")

    try:
        # 시총 상위 5개 코인 조회
        res = requests.get(
            "https://api.coingecko.com/api/v3/coins/markets",
            params={
                "vs_currency": "usd",
                "order": "market_cap_desc",
                "per_page": 5,
                "page": 1,
                "sparkline": "false",
                "price_change_percentage": "1h,24h,7d,30d",
            },
            timeout=10,
        )
        res.raise_for_status()
        coins_data = res.json()

        # period에 맞는 등락률 필드 선택
        pct_field_map = {
            "1d": "price_change_percentage_24h",
            "1w": "price_change_percentage_7d_in_currency",
            "1mo": "price_change_percentage_30d_in_currency",
            "ytd": "price_change_percentage_24h",  # fallback: 별도 계산 필요
        }
        pct_field = pct_field_map.get(period, "price_change_percentage_24h")

        result = []
        for coin in coins_data:
            change = coin.get(pct_field)
            if change is None:
                change = coin.get("price_change_percentage_24h", 0)

            result.append({
                "ticker": coin["symbol"].upper(),
                "name": coin["name"],
                "market_cap": coin.get("market_cap", 0),
                "change_pct": round(change, 2) if change else 0,
            })

        return result
    except Exception as e:
        print(f"[Market] CoinGecko 코인 데이터 실패: {e}")
        return []


def _fetch_commodity_heatmap(period: str) -> List[Dict[str, Any]]:
    """금, 은, WTI 원자재 등락률 반환."""
    commodities = [
        {"yf_ticker": "GC=F", "name": "금", "display_ticker": "GOLD"},
        {"yf_ticker": "SI=F", "name": "은", "display_ticker": "SILVER"},
        {"yf_ticker": "CL=F", "name": "WTI", "display_ticker": "WTI"},
    ]

    yf_period = _period_to_yf(period)
    result = []

    for c in commodities:
        try:
            hist = yf.Ticker(c["yf_ticker"]).history(period=yf_period)
            if hist.empty or len(hist) < 2:
                continue

            close_first = float(hist["Close"].iloc[0])
            close_last = float(hist["Close"].iloc[-1])

            if close_first <= 0:
                continue

            change_pct = ((close_last - close_first) / close_first) * 100

            result.append({
                "ticker": c["display_ticker"],
                "name": c["name"],
                "change_pct": round(change_pct, 2),
            })
        except Exception as e:
            print(f"[Market] 원자재 {c['name']} 실패: {e}")
            continue

    return result
```

- [ ] **Step 2: 히트맵 데이터 수집 테스트**

Run: `cd backend && python -c "from services.market import fetch_heatmap_data; d = fetch_heatmap_data('1d'); print(f'stocks={len(d[\"stocks\"])}, coins={len(d[\"coins\"])}, commodities={len(d[\"commodities\"])]}')"`
Expected: `stocks=~500, coins=5, commodities=3` 유사한 출력. 시간이 좀 걸릴 수 있음 (첫 호출 시 30초~1분).

**참고**: `_fetch_stock_heatmap`에서 각 종목의 `fast_info.marketCap`을 개별 호출하면 500번 호출로 너무 느릴 수 있음. 속도가 문제되면 시가총액을 한 번에 가져오는 방식으로 변경해야 함 — 아래 Step 3 참고.

- [ ] **Step 3: 시가총액 일괄 조회 최적화**

500종목 개별 `fast_info` 호출은 너무 느림. `yf.Tickers`를 사용하거나, Wikipedia에서 가져온 종목 순서(이미 대략적 시가총액 순)를 활용하여 고정 시가총액 데이터를 사용하는 방식으로 변경.

`_fetch_stock_heatmap` 함수의 시가총액 부분을 다음으로 교체:

```python
def _fetch_stock_heatmap(period: str) -> List[Dict[str, Any]]:
    """S&P500 전체 종목의 등락률 + 시가총액 반환."""
    sp500 = get_sp500_list()
    if not sp500:
        return []

    tickers = [s["ticker"] for s in sp500]
    sector_map = {s["ticker"]: s["sector"] for s in sp500}
    name_map = {s["ticker"]: s["name"] for s in sp500}

    yf_period = _period_to_yf(period)

    try:
        data = yf.download(tickers, period=yf_period, group_by="ticker", threads=True, progress=False)
        if data.empty:
            return []

        # 시가총액: 마지막 종가 * 발행주식수가 필요하지만 배치로 안 됨
        # 대안: yf.download에서 Volume * Close를 proxy로 쓰거나,
        # 별도 배치로 market_cap을 한 번만 가져와서 캐시
        market_caps = _get_sp500_market_caps(tickers)

        result = []
        for ticker in tickers:
            try:
                ticker_data = data[ticker] if len(tickers) > 1 else data
                if ticker_data.empty or len(ticker_data) < 2:
                    continue

                close_first = float(ticker_data["Close"].iloc[0])
                close_last = float(ticker_data["Close"].iloc[-1])
                if close_first <= 0:
                    continue

                change_pct = ((close_last - close_first) / close_first) * 100
                result.append({
                    "ticker": ticker,
                    "name": name_map.get(ticker, ticker),
                    "sector": sector_map.get(ticker, "Unknown"),
                    "market_cap": market_caps.get(ticker, 0),
                    "change_pct": round(change_pct, 2),
                })
            except Exception:
                continue

        print(f"[Market] S&P500 히트맵 데이터: {len(result)}개 종목 (period={period})")
        return result
    except Exception as e:
        print(f"[Market] S&P500 다운로드 실패: {e}")
        return []


_mcap_cache: Dict[str, Any] = {}  # {"data": {ticker: mcap}, "fetched_at": datetime}
MCAP_TTL = 86400  # 24시간


def _get_sp500_market_caps(tickers: List[str]) -> Dict[str, float]:
    """S&P500 시가총액을 일괄 조회 (24시간 캐시).

    yfinance의 Tickers 객체를 사용하여 배치 처리.
    """
    now = datetime.utcnow()
    if _mcap_cache.get("data") and _mcap_cache.get("fetched_at"):
        if (now - _mcap_cache["fetched_at"]).total_seconds() < MCAP_TTL:
            return _mcap_cache["data"]

    print("[Market] S&P500 시가총액 일괄 조회 시작...")
    result = {}
    # 50개씩 배치로 처리
    batch_size = 50
    for i in range(0, len(tickers), batch_size):
        batch = tickers[i:i + batch_size]
        try:
            tickers_obj = yf.Tickers(" ".join(batch))
            for ticker in batch:
                try:
                    info = tickers_obj.tickers[ticker].fast_info
                    result[ticker] = info.get("marketCap", 0) or 0
                except Exception:
                    result[ticker] = 0
        except Exception:
            for ticker in batch:
                result[ticker] = 0

    _mcap_cache["data"] = result
    _mcap_cache["fetched_at"] = now
    print(f"[Market] 시가총액 조회 완료: {len(result)}개")
    return result
```

- [ ] **Step 4: 커밋**

```bash
git add backend/services/market.py
git commit -m "feat(market): add heatmap data fetcher for stocks, coins, commodities"
```

---

### Task 3: 위젯 지표 수집 함수

**Files:**
- Modify: `backend/services/market.py`

- [ ] **Step 1: 위젯 지표 수집 함수 작성**

`backend/services/market.py`에 8개 위젯 지표 데이터를 수집하는 함수를 추가한다.

```python
def fetch_market_indicators() -> Dict[str, Any]:
    """시장 지표 위젯 데이터 수집. 캐시 10분.

    Returns: {fear_greed, usd_krw, btc_dominance, vix, dxy, us10y, kimchi_premium, jpy_krw}
    각 항목에 value, change_pct(또는 change), sparkline(7일) 포함.
    """
    now = datetime.utcnow()
    cached = _indicators_cache
    if cached.get("data") and cached.get("fetched_at"):
        if (now - cached["fetched_at"]).total_seconds() < INDICATORS_TTL:
            return cached["data"]

    result = {}
    result["fear_greed"] = _fetch_fear_greed()
    result["usd_krw"] = _fetch_yf_indicator("USDKRW=X", "USD/KRW")
    result["jpy_krw"] = _fetch_yf_indicator("JPYKRW=X", "JPY/KRW")
    result["vix"] = _fetch_yf_indicator("^VIX", "VIX")
    result["dxy"] = _fetch_yf_indicator("DX-Y.NYB", "DXY")
    result["us10y"] = _fetch_yf_indicator("^TNX", "US 10Y")
    result["btc_dominance"] = _fetch_btc_dominance()
    result["kimchi_premium"] = _fetch_kimchi_premium(
        result.get("usd_krw", {}).get("value")
    )

    _indicators_cache["data"] = result
    _indicators_cache["fetched_at"] = now
    return result


def _fetch_yf_indicator(yf_ticker: str, label: str) -> Dict[str, Any]:
    """yfinance에서 단일 지표의 현재값 + 등락률 + 7일 스파크라인."""
    try:
        hist = yf.Ticker(yf_ticker).history(period="10d")
        if hist.empty or len(hist) < 2:
            return {"value": None, "change_pct": None, "sparkline": []}

        closes = [float(c) for c in hist["Close"].tolist()]
        current = closes[-1]
        prev = closes[-2]

        change_pct = ((current - prev) / prev) * 100 if prev != 0 else 0

        # 최근 7개 데이터포인트를 스파크라인으로
        sparkline = [round(c, 4) for c in closes[-7:]]

        return {
            "value": round(current, 2),
            "change_pct": round(change_pct, 2),
            "sparkline": sparkline,
        }
    except Exception as e:
        print(f"[Market] {label} ({yf_ticker}) 조회 실패: {e}")
        return {"value": None, "change_pct": None, "sparkline": []}


def _fetch_fear_greed() -> Dict[str, Any]:
    """Alternative.me 공포·탐욕 지수 + 7일 스파크라인."""
    try:
        res = requests.get(
            "https://api.alternative.me/fng/",
            params={"limit": 7},
            timeout=5,
        )
        res.raise_for_status()
        data_list = res.json()["data"]

        current = data_list[0]
        # API는 최신순이므로 reverse하여 시간순으로
        sparkline = [int(d["value"]) for d in reversed(data_list)]

        return {
            "value": int(current["value"]),
            "label": current["value_classification"],
            "sparkline": sparkline,
        }
    except Exception as e:
        print(f"[Market] 공포탐욕지수 조회 실패: {e}")
        return {"value": None, "label": None, "sparkline": []}


def _fetch_btc_dominance() -> Dict[str, Any]:
    """CoinGecko에서 BTC 도미넌스 조회."""
    try:
        res = requests.get(
            "https://api.coingecko.com/api/v3/global",
            timeout=10,
        )
        res.raise_for_status()
        global_data = res.json()["data"]

        btc_dom = global_data["market_cap_percentage"]["btc"]

        # CoinGecko /global에는 히스토리가 없으므로 스파크라인은 현재값만
        return {
            "value": round(btc_dom, 1),
            "change_pct": None,  # 히스토리 없이 단일 값
            "sparkline": [round(btc_dom, 1)],
        }
    except Exception as e:
        print(f"[Market] BTC 도미넌스 조회 실패: {e}")
        return {"value": None, "change_pct": None, "sparkline": []}


def _fetch_kimchi_premium(usd_krw_rate: Optional[float] = None) -> Dict[str, Any]:
    """김치프리미엄 계산: (업비트 BTC/KRW - 바이낸스 BTC/USD * USD/KRW) / (바이낸스 BTC/USD * USD/KRW) * 100."""
    try:
        # 업비트 BTC/KRW
        upbit_res = requests.get(
            "https://api.upbit.com/v1/ticker",
            params={"markets": "KRW-BTC"},
            timeout=5,
        )
        upbit_res.raise_for_status()
        upbit_btc_krw = upbit_res.json()[0]["trade_price"]

        # CoinGecko BTC/USD
        cg_res = requests.get(
            "https://api.coingecko.com/api/v3/simple/price",
            params={"ids": "bitcoin", "vs_currencies": "usd"},
            timeout=5,
        )
        cg_res.raise_for_status()
        btc_usd = cg_res.json()["bitcoin"]["usd"]

        # USD/KRW 환율
        if not usd_krw_rate:
            from services.stock import get_usd_krw
            usd_krw_rate = get_usd_krw() or 1350

        global_btc_krw = btc_usd * usd_krw_rate
        premium = ((upbit_btc_krw - global_btc_krw) / global_btc_krw) * 100

        return {
            "value": round(premium, 2),
            "change_pct": None,  # 히스토리 없이 현재값만
            "sparkline": [round(premium, 2)],
        }
    except Exception as e:
        print(f"[Market] 김치프리미엄 계산 실패: {e}")
        return {"value": None, "change_pct": None, "sparkline": []}
```

- [ ] **Step 2: 위젯 지표 수집 테스트**

Run: `cd backend && python -c "from services.market import fetch_market_indicators; import json; d = fetch_market_indicators(); print(json.dumps({k: v.get('value') for k, v in d.items()}, indent=2))"`
Expected: 각 지표의 현재값이 출력됨 (일부 None 가능).

- [ ] **Step 3: 커밋**

```bash
git add backend/services/market.py
git commit -m "feat(market): add market indicators fetcher (widgets with sparklines)"
```

---

### Task 4: Market API 라우터

**Files:**
- Create: `backend/routers/market.py`
- Modify: `backend/main.py`

- [ ] **Step 1: market 라우터 작성**

```python
"""시장 상황판 API 라우터."""
from typing import Any, Dict

from fastapi import APIRouter, Query

from services.market import fetch_heatmap_data, fetch_market_indicators

router = APIRouter(prefix="/api/market")


@router.get("/heatmap")
def get_heatmap(period: str = Query(default="1d", regex="^(1d|1w|1mo|ytd)$")) -> Dict[str, Any]:
    """히트맵 데이터 반환.

    period: 1d (당일), 1w (1주), 1mo (1개월), ytd (연초대비)
    """
    return fetch_heatmap_data(period)


@router.get("/indicators")
def get_indicators() -> Dict[str, Any]:
    """시장 지표 위젯 데이터 반환."""
    return fetch_market_indicators()
```

- [ ] **Step 2: main.py에 라우터 등록**

`backend/main.py` 상단 import 부분에 추가:

```python
from routers.market import router as market_router
```

라우터 등록 부분에 추가 (news_router 다음):

```python
app.include_router(market_router,    dependencies=[Depends(require_auth)])   # /api/market/* (인증 필요)
```

- [ ] **Step 3: 서버 시작하여 API 테스트**

Run: `cd backend && uvicorn main:app --reload &`

그리고 별도 터미널에서:

Run: `curl -s http://localhost:8000/api/market/indicators -H "Authorization: Bearer <TOKEN>" | python -m json.tool | head -20`

Expected: JSON 응답으로 지표 데이터가 반환됨 (인증 없이 401 반환 확인도).

- [ ] **Step 4: 커밋**

```bash
git add backend/routers/market.py backend/main.py
git commit -m "feat(market): add /api/market/heatmap and /api/market/indicators endpoints"
```

---

### Task 5: 프론트엔드 — market.html 페이지 기본 구조

**Files:**
- Create: `frontend/market.html`

- [ ] **Step 1: market.html 기본 골격 작성**

기존 `news.html`과 동일한 사이드바/레이아웃 구조를 사용하되, 메인 컨텐츠 영역에 히트맵 컨테이너 + 위젯 그리드를 배치. D3.js CDN 추가.

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>시장 상황판 — My Portfolio</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        :root {
            --color-up: #16a34a;
            --color-down: #dc2626;
            --color-neutral: #6b7280;
            --bg-main: #f1f5f9;
            --card-radius: 0.875rem;
        }
        body { background: var(--bg-main); font-family: 'Inter', sans-serif; color: #1e293b; }
        .navbar { box-shadow: 0 1px 3px rgba(0,0,0,.08); }
        .section-card {
            border: none; border-radius: var(--card-radius);
            box-shadow: 0 1px 4px rgba(0,0,0,.06);
        }
        .section-title {
            font-size: .8rem; font-weight: 600; letter-spacing: .06em;
            text-transform: uppercase; color: #64748b; margin-bottom: 1rem;
        }

        /* ── Sidebar (기존 페이지와 동일) ── */
        #sidebar {
            position: fixed; top: 0; left: 0; bottom: 0; width: 240px;
            background: #fff; border-right: 1px solid #e2e8f0;
            padding: 1.25rem 0; z-index: 1040; overflow-y: auto;
        }
        body.has-sidebar > nav.navbar,
        body.has-sidebar > #main-content { margin-left: 240px; }
        .sidebar-link {
            display: flex; align-items: center;
            padding: .55rem 1.25rem; color: #64748b;
            text-decoration: none; font-size: .85rem; font-weight: 500;
            transition: background .15s;
        }
        .sidebar-link:hover:not(.disabled) { background: #f8fafc; color: #0f172a; }
        .sidebar-link.active {
            background: #eff6ff; color: #2563eb;
            border-right: 3px solid #2563eb;
        }
        .sidebar-link.disabled { color: #cbd5e1; cursor: not-allowed; }
        .sidebar-link .badge { margin-left: auto; }

        /* ── 히트맵 ── */
        #heatmap-container {
            width: 100%;
            min-height: 500px;
            background: #1a1a2e;
            border-radius: var(--card-radius);
            overflow: hidden;
        }
        .period-tabs .btn { font-size: .8rem; }
        .period-tabs .btn.active {
            background: #2563eb; color: #fff; border-color: #2563eb;
        }

        /* ── 위젯 카드 ── */
        .indicator-card {
            background: #fff; border-radius: var(--card-radius);
            padding: 1rem 1.25rem;
            box-shadow: 0 1px 4px rgba(0,0,0,.06);
        }
        .indicator-card .label { font-size: .72rem; color: #94a3b8; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
        .indicator-card .value { font-size: 1.35rem; font-weight: 700; color: #1e293b; }
        .indicator-card .change { font-size: .75rem; font-weight: 600; }
        .text-up { color: var(--color-up) !important; }
        .text-down { color: var(--color-down) !important; }
        .text-neutral { color: var(--color-neutral) !important; }

        /* ── 트리맵 셀 ── */
        .treemap-cell {
            position: absolute;
            overflow: hidden;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            border: 1px solid rgba(0,0,0,.3);
            font-family: 'Inter', sans-serif;
            cursor: default;
            transition: opacity .15s;
        }
        .treemap-cell:hover { opacity: .85; }
        .treemap-cell .cell-ticker { font-size: 11px; font-weight: 700; color: #fff; }
        .treemap-cell .cell-change { font-size: 10px; color: rgba(255,255,255,.85); }
        .treemap-cell .cell-name { font-size: 9px; color: rgba(255,255,255,.6); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 90%; }

        .sector-label {
            position: absolute; top: 2px; left: 4px;
            font-size: 10px; font-weight: 700; color: rgba(255,255,255,.5);
            text-transform: uppercase; pointer-events: none;
            z-index: 10;
        }

        @media (max-width: 991.98px) {
            #sidebar { display: none; }
            body.has-sidebar > nav.navbar,
            body.has-sidebar > #main-content { margin-left: 0; }
        }
    </style>
</head>
<body class="has-sidebar">

<!-- ── Sidebar ── -->
<aside id="sidebar">
    <div class="px-3 mb-3"><span class="fw-bold"><i class="bi bi-wallet2 me-2"></i>My Portfolio</span></div>
    <hr class="mx-3 my-2">
    <nav>
        <a href="/" class="sidebar-link"><i class="bi bi-speedometer2 me-2"></i>대시보드</a>
        <div class="px-3 mt-3 mb-1" style="font-size:.7rem;font-weight:700;color:#94a3b8;letter-spacing:.06em;text-transform:uppercase;">분석</div>
        <a href="/news.html" class="sidebar-link"><i class="bi bi-newspaper me-2"></i>뉴스 리포트</a>
        <a href="/market.html" class="sidebar-link active"><i class="bi bi-globe me-2"></i>시장 상황판</a>
        <div class="px-3 mt-3 mb-1" style="font-size:.7rem;font-weight:700;color:#94a3b8;letter-spacing:.06em;text-transform:uppercase;">도구</div>
        <span class="sidebar-link disabled">가격 알림 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">리밸런싱 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">트레이드 저널 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">수익 실현 계산기 <span class="badge text-bg-light">준비중</span></span>
        <div class="px-3 mt-3 mb-1" style="font-size:.7rem;font-weight:700;color:#94a3b8;letter-spacing:.06em;text-transform:uppercase;">설정</div>
        <span class="sidebar-link disabled">설정 <span class="badge text-bg-light">준비중</span></span>
    </nav>
</aside>

<!-- ── Navbar ── -->
<nav class="navbar navbar-light bg-white py-2">
    <div class="container-fluid">
        <span class="navbar-brand fw-bold d-lg-none"><i class="bi bi-wallet2 me-2"></i>My Portfolio</span>
        <span class="navbar-text ms-auto text-muted" style="font-size:.8rem;" id="last-updated"></span>
    </div>
</nav>

<!-- ── Main Content ── -->
<div id="main-content" class="container-fluid py-4" style="max-width:1400px;">
    <!-- 기간 탭 -->
    <div class="d-flex justify-content-between align-items-center mb-3">
        <h5 class="mb-0 fw-bold"><i class="bi bi-globe me-2"></i>시장 상황판</h5>
        <div class="period-tabs btn-group" role="group">
            <button type="button" class="btn btn-outline-secondary btn-sm active" data-period="1d">1일</button>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-period="1w">1주</button>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-period="1mo">1개월</button>
            <button type="button" class="btn btn-outline-secondary btn-sm" data-period="ytd">YTD</button>
        </div>
    </div>

    <!-- 히트맵 -->
    <div class="card section-card mb-4">
        <div class="card-body p-0">
            <div id="heatmap-container">
                <div id="heatmap-loading" class="d-flex align-items-center justify-content-center" style="min-height:500px;">
                    <div class="spinner-border text-light" role="status"></div>
                    <span class="text-light ms-3">히트맵 데이터 로딩 중...</span>
                </div>
            </div>
        </div>
    </div>

    <!-- 위젯 그리드 -->
    <div class="section-title">시장 지표</div>
    <div class="row g-3 mb-4" id="indicators-grid">
        <!-- JS로 동적 생성 -->
    </div>
</div>

<script>
// ── Auth ──
const TOKEN_KEY = 'portfolio_token';
function getToken() { return localStorage.getItem(TOKEN_KEY); }
function apiFetch(url, opts = {}) {
    const token = getToken();
    if (!token) { window.location.href = '/login.html'; return Promise.reject('No token'); }
    return fetch(url, {
        ...opts,
        headers: { 'Authorization': `Bearer ${token}`, ...(opts.headers || {}) }
    }).then(r => {
        if (r.status === 401) { localStorage.removeItem(TOKEN_KEY); window.location.href = '/login.html'; }
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
    });
}

// ── 색상 스케일 ──
function changeColor(pct) {
    if (pct == null) return '#374151';
    if (pct >= 3)  return '#15803d';
    if (pct >= 1)  return '#22c55e';
    if (pct > -1)  return '#4b5563';
    if (pct > -3)  return '#ef4444';
    return '#b91c1c';
}

// ── 히트맵 렌더링 (D3 treemap) ──
let currentPeriod = '1d';

async function loadHeatmap(period) {
    currentPeriod = period;
    const container = document.getElementById('heatmap-container');
    container.innerHTML = '<div class="d-flex align-items-center justify-content-center" style="min-height:500px;"><div class="spinner-border text-light"></div><span class="text-light ms-3">히트맵 데이터 로딩 중...</span></div>';

    try {
        const data = await apiFetch(`/api/market/heatmap?period=${period}`);
        renderTreemap(data, container);
    } catch (e) {
        container.innerHTML = '<div class="d-flex align-items-center justify-content-center" style="min-height:500px;"><span class="text-danger">히트맵 데이터를 불러올 수 없습니다.</span></div>';
        console.error('heatmap error:', e);
    }
}

function renderTreemap(data, container) {
    container.innerHTML = '';
    const width = container.clientWidth;
    const height = 500;
    container.style.position = 'relative';
    container.style.height = height + 'px';

    // 3개 섹터를 하나의 계층 구조로 변환
    const children = [];

    // 주식: 섹터별 그룹
    const sectorGroups = {};
    (data.stocks || []).forEach(s => {
        if (!sectorGroups[s.sector]) sectorGroups[s.sector] = [];
        sectorGroups[s.sector].push(s);
    });
    Object.entries(sectorGroups).forEach(([sector, stocks]) => {
        children.push({
            name: sector,
            type: 'sector',
            children: stocks.map(s => ({
                name: s.ticker,
                fullName: s.name,
                value: Math.max(s.market_cap || 1, 1),
                change_pct: s.change_pct,
                type: 'stock',
            }))
        });
    });

    // 코인
    if (data.coins && data.coins.length > 0) {
        children.push({
            name: 'Crypto',
            type: 'sector',
            children: data.coins.map(c => ({
                name: c.ticker,
                fullName: c.name,
                value: Math.max(c.market_cap || 1, 1),
                change_pct: c.change_pct,
                type: 'coin',
            }))
        });
    }

    // 원자재
    if (data.commodities && data.commodities.length > 0) {
        children.push({
            name: 'Commodities',
            type: 'sector',
            children: data.commodities.map(c => ({
                name: c.ticker,
                fullName: c.name,
                value: 1,  // 균등 크기
                change_pct: c.change_pct,
                type: 'commodity',
            }))
        });
    }

    const root = d3.hierarchy({ name: 'Market', children })
        .sum(d => d.value || 0)
        .sort((a, b) => (b.value || 0) - (a.value || 0));

    d3.treemap()
        .size([width, height])
        .paddingTop(18)
        .paddingInner(2)
        .paddingOuter(2)
        (root);

    // 섹터 라벨
    root.children?.forEach(sector => {
        const label = document.createElement('div');
        label.className = 'sector-label';
        label.style.left = sector.x0 + 4 + 'px';
        label.style.top = sector.y0 + 2 + 'px';
        label.textContent = sector.data.name;
        container.appendChild(label);
    });

    // 셀 렌더링
    const leaves = root.leaves();
    leaves.forEach(leaf => {
        const w = leaf.x1 - leaf.x0;
        const h = leaf.y1 - leaf.y0;
        if (w < 2 || h < 2) return;

        const cell = document.createElement('div');
        cell.className = 'treemap-cell';
        cell.style.left = leaf.x0 + 'px';
        cell.style.top = leaf.y0 + 'px';
        cell.style.width = w + 'px';
        cell.style.height = h + 'px';
        cell.style.backgroundColor = changeColor(leaf.data.change_pct);
        cell.title = `${leaf.data.fullName || leaf.data.name}\n${leaf.data.change_pct != null ? (leaf.data.change_pct >= 0 ? '+' : '') + leaf.data.change_pct + '%' : 'N/A'}`;

        // 셀 크기에 따라 표시 내용 조정
        if (w > 40 && h > 25) {
            const ticker = document.createElement('div');
            ticker.className = 'cell-ticker';
            ticker.textContent = leaf.data.name;
            cell.appendChild(ticker);
        }
        if (w > 35 && h > 35) {
            const change = document.createElement('div');
            change.className = 'cell-change';
            const pct = leaf.data.change_pct;
            change.textContent = pct != null ? (pct >= 0 ? '+' : '') + pct.toFixed(1) + '%' : '';
            cell.appendChild(change);
        }
        if (w > 70 && h > 50) {
            const name = document.createElement('div');
            name.className = 'cell-name';
            name.textContent = leaf.data.fullName || '';
            cell.appendChild(name);
        }

        container.appendChild(cell);
    });
}

// ── 위젯 지표 ──
async function loadIndicators() {
    try {
        const data = await apiFetch('/api/market/indicators');
        const grid = document.getElementById('indicators-grid');
        grid.innerHTML = '';

        const widgets = [
            { key: 'fear_greed', label: '공포·탐욕', format: v => v, suffix: '', showLabel: true },
            { key: 'usd_krw', label: 'USD/KRW', format: v => v?.toLocaleString('ko-KR'), prefix: '₩' },
            { key: 'btc_dominance', label: 'BTC 도미넌스', format: v => v, suffix: '%' },
            { key: 'vix', label: 'VIX', format: v => v },
            { key: 'dxy', label: 'DXY', format: v => v },
            { key: 'us10y', label: 'US 10Y', format: v => v, suffix: '%' },
            { key: 'kimchi_premium', label: '김치프리미엄', format: v => v, suffix: '%' },
            { key: 'jpy_krw', label: 'JPY/KRW', format: v => v },
        ];

        widgets.forEach(w => {
            const d = data[w.key] || {};
            const val = d.value;
            const changePct = d.change_pct;
            const sparkline = d.sparkline || [];

            const changeClass = changePct > 0 ? 'text-up' : changePct < 0 ? 'text-down' : 'text-neutral';
            const changeText = changePct != null ? (changePct >= 0 ? '▲' : '▼') + ' ' + Math.abs(changePct).toFixed(1) + '%' : '';

            // 공포탐욕 라벨
            let subLabel = '';
            if (w.key === 'fear_greed' && d.label) {
                subLabel = `<div class="change ${fngColor(val)}">${d.label}</div>`;
            } else {
                subLabel = `<div class="change ${changeClass}">${changeText}</div>`;
            }

            // 스파크라인 SVG
            const sparkSvg = renderSparkline(sparkline, changePct);

            const col = document.createElement('div');
            col.className = 'col-6 col-md-3';
            col.innerHTML = `
                <div class="indicator-card">
                    <div class="label">${w.label}</div>
                    <div class="d-flex justify-content-between align-items-center mt-1">
                        <div>
                            <div class="value">${val != null ? (w.prefix || '') + w.format(val) + (w.suffix || '') : '—'}</div>
                            ${subLabel}
                        </div>
                        ${sparkSvg}
                    </div>
                </div>
            `;
            grid.appendChild(col);
        });
    } catch (e) {
        console.error('indicators error:', e);
    }
}

function fngColor(val) {
    if (val == null) return 'text-neutral';
    if (val <= 25) return 'text-down';
    if (val <= 45) return 'text-neutral';
    if (val <= 55) return 'text-neutral';
    return 'text-up';
}

function renderSparkline(data, changePct) {
    if (!data || data.length < 2) return '';
    const w = 60, h = 28, pad = 2;
    const min = Math.min(...data);
    const max = Math.max(...data);
    const range = max - min || 1;

    const points = data.map((v, i) => {
        const x = pad + (i / (data.length - 1)) * (w - pad * 2);
        const y = pad + (1 - (v - min) / range) * (h - pad * 2);
        return `${x.toFixed(1)},${y.toFixed(1)}`;
    }).join(' ');

    const color = changePct > 0 ? 'var(--color-up)' : changePct < 0 ? 'var(--color-down)' : 'var(--color-neutral)';

    return `<svg width="${w}" height="${h}" style="opacity:.6;">
        <polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.5"/>
    </svg>`;
}

// ── 기간 탭 이벤트 ──
document.querySelectorAll('.period-tabs .btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.period-tabs .btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        loadHeatmap(btn.dataset.period);
    });
});

// ── 초기 로드 ──
document.addEventListener('DOMContentLoaded', () => {
    if (!getToken()) { window.location.href = '/login.html'; return; }
    loadHeatmap('1d');
    loadIndicators();
    document.getElementById('last-updated').textContent = '업데이트: ' + new Date().toLocaleString('ko-KR');
});
</script>
</body>
</html>
```

이 파일은 길지만 하나의 자기 완결적 HTML 페이지이므로 분할하지 않는다 (기존 index.html, news.html과 동일한 패턴).

- [ ] **Step 2: 브라우저에서 확인**

서버가 실행 중인 상태에서 `http://localhost:8000/market.html` 접속.

확인 항목:
1. 사이드바가 정상 표시되고 "시장 상황판"이 active 상태인지
2. 히트맵 로딩 스피너가 나타나는지
3. 데이터 로드 후 트리맵이 렌더링되는지
4. 기간 탭 클릭 시 히트맵이 재로딩되는지
5. 위젯 카드 8개가 하단에 표시되는지
6. 스파크라인이 각 카드에 표시되는지

- [ ] **Step 3: 커밋**

```bash
git add frontend/market.html
git commit -m "feat(market): add market overview page with treemap heatmap and indicator widgets"
```

---

### Task 6: 사이드바 링크 활성화

**Files:**
- Modify: `frontend/index.html:193`
- Modify: `frontend/news.html:202`
- Modify: `frontend/detail.html` (해당 라인 확인 필요)

- [ ] **Step 1: index.html 사이드바 수정**

`frontend/index.html` 193행의:

```html
<span class="sidebar-link disabled">시장 상황판 <span class="badge text-bg-light">준비중</span></span>
```

를 다음으로 변경:

```html
<a href="/market.html" class="sidebar-link"><i class="bi bi-globe me-2"></i>시장 상황판</a>
```

- [ ] **Step 2: news.html 사이드바 수정**

`frontend/news.html` 202행의:

```html
<span class="sidebar-link disabled">시장 상황판 <span class="badge text-bg-light">준비중</span></span>
```

를 다음으로 변경:

```html
<a href="/market.html" class="sidebar-link"><i class="bi bi-globe me-2"></i>시장 상황판</a>
```

- [ ] **Step 3: detail.html 사이드바 수정 (존재하는 경우)**

`frontend/detail.html`에도 동일한 "시장 상황판 준비중" 라인이 있는지 확인하고, 있으면 동일하게 변경:

```html
<a href="/market.html" class="sidebar-link"><i class="bi bi-globe me-2"></i>시장 상황판</a>
```

- [ ] **Step 4: 브라우저에서 사이드바 네비게이션 테스트**

각 페이지에서 시장 상황판 링크 클릭 시 `/market.html`로 정상 이동하는지 확인.

- [ ] **Step 5: 커밋**

```bash
git add frontend/index.html frontend/news.html frontend/detail.html
git commit -m "feat(market): activate market overview sidebar link across all pages"
```

---

### Task 7: 통합 테스트 및 마무리

**Files:**
- 수정 없음 (전체 동작 검증)

- [ ] **Step 1: 서버 재시작하여 전체 테스트**

Run: `cd backend && uvicorn main:app --reload`

- [ ] **Step 2: API 엔드포인트 테스트**

1. `GET /api/market/heatmap?period=1d` — stocks/coins/commodities 키가 있는 JSON 응답
2. `GET /api/market/heatmap?period=1w` — 1주 데이터
3. `GET /api/market/indicators` — 8개 위젯 키가 있는 JSON 응답
4. 인증 없이 접근 시 401 응답 확인

- [ ] **Step 3: 브라우저 전체 기능 확인**

1. 로그인 → 대시보드 → 사이드바에서 "시장 상황판" 클릭
2. 히트맵 렌더링 확인 (S&P500 섹터별 그룹, 코인, 원자재)
3. 기간 탭(1일/1주/1개월/YTD) 전환 시 히트맵 재로딩
4. 히트맵 셀 hover 시 종목명/등락률 tooltip
5. 하단 위젯 8개 카드 표시 + 스파크라인
6. 모바일 뷰에서 사이드바 숨김, 히트맵 반응형 동작

- [ ] **Step 4: 에러 케이스 확인**

1. 네트워크 끊김 시 "데이터를 불러올 수 없습니다" 메시지
2. 부분 실패 (CoinGecko 실패해도 주식 히트맵은 표시)

- [ ] **Step 5: 최종 커밋 (필요시)**

변경 사항이 있으면 커밋.

```bash
git add -A
git commit -m "fix(market): polish and integration fixes"
```
