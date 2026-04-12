# Phase 2: 종목별 상세 정보 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보유 주식(미국) 상세 정보 페이지 구현 + 코인/주식 통합 상세 페이지 + 대시보드 어닝 캘린더

**Architecture:** yfinance로 주식 데이터 조회하는 백엔드 서비스+라우터 추가. 기존 `detail.html`을 `type` URL 파라미터로 코인/주식 분기. 대시보드에 어닝 캘린더 섹션 삽입. 주식 보유 정보는 기존 `ManualAsset` 테이블 패턴으로 `StockHolding` 테이블 추가.

**Tech Stack:** Python 3.9, FastAPI, yfinance, SQLAlchemy (SQLite), vanilla HTML/CSS/JS, Chart.js, Bootstrap 5

---

## File Structure

| Action | Path | Responsibility |
|--------|------|----------------|
| Create | `backend/services/stock.py` | yfinance 래퍼: 종목 상세, 가격 히스토리, 어닝 날짜, 환율 조회 |
| Create | `backend/routers/stock.py` | 주식 API 엔드포인트: `/api/stock/{ticker}`, `/api/stock/{ticker}/price-history`, `/api/earnings-calendar` |
| Modify | `backend/database.py` | `StockHolding` 모델 추가 + 마이그레이션 |
| Modify | `backend/main.py` | stock 라우터 등록 |
| Modify | `backend/requirements.txt` | yfinance 추가 |
| Modify | `backend/scheduler.py` | 주식 자산을 포트폴리오 동기화에 포함 + 환율 캐시 |
| Modify | `backend/routers/portfolio.py` | AssetOut에 currency 필드 추가 |
| Modify | `frontend/detail.html` | 통합 상세 페이지 (type 파라미터 분기, 주식 섹션 추가) |
| Modify | `frontend/index.html` | 어닝 캘린더 섹션 + 주식 행 클릭 링크 |

---

### Task 1: yfinance 의존성 추가

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: requirements.txt에 yfinance 추가**

`backend/requirements.txt` 맨 끝에 한 줄 추가:

```
yfinance
```

- [ ] **Step 2: 설치**

Run: `cd backend && source venv/bin/activate && pip install yfinance`

- [ ] **Step 3: import 확인**

Run: `cd backend && source venv/bin/activate && python -c "import yfinance; print(yfinance.__version__)"`
Expected: 버전 번호 출력, 에러 없음

- [ ] **Step 4: Commit**

```bash
git add backend/requirements.txt
git commit -m "chore: add yfinance dependency for stock data"
```

---

### Task 2: StockHolding DB 모델

**Files:**
- Modify: `backend/database.py:88-102` (ManualAsset 클래스 뒤에 추가)

- [ ] **Step 1: StockHolding 모델 추가**

`backend/database.py`에서 `ManualAsset` 클래스 뒤, `init_db()` 함수 앞에 추가:

```python
class StockHolding(Base):
    """미국 주식 보유 정보 (수동 등록)."""
    __tablename__ = "stock_holdings"

    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False, unique=True)   # 예: AAPL
    name = Column(String(100), nullable=False)                  # 예: Apple Inc.
    quantity = Column(Float, nullable=False)
    avg_price = Column(Float, nullable=False)                   # USD
    first_purchase_date = Column(DateTime, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
```

- [ ] **Step 2: init_db()에서 테이블 자동 생성 확인**

`init_db()`의 `Base.metadata.create_all(bind=engine)`이 이미 모든 모델을 처리하므로 추가 코드 불필요. 단, `StockHolding`이 `Base`를 상속하는지 확인.

Run: `cd backend && source venv/bin/activate && python -c "from database import init_db; init_db(); print('OK')"`
Expected: `OK` 출력, `portfolio.db`에 `stock_holdings` 테이블 생성됨

- [ ] **Step 3: 테스트 데이터 삽입 스크립트 실행**

보유 주식 데이터를 직접 DB에 삽입. 유저가 실제 보유 종목으로 교체할 수 있도록 예시 데이터:

Run:
```bash
cd backend && source venv/bin/activate && python -c "
from database import engine, StockHolding, init_db
from sqlalchemy.orm import Session
from datetime import datetime

init_db()
with Session(engine) as db:
    # 이미 있으면 스킵
    if not db.query(StockHolding).first():
        db.add(StockHolding(
            ticker='AAPL', name='Apple Inc.',
            quantity=10, avg_price=150.0,
            first_purchase_date=datetime(2024, 1, 15),
        ))
        db.add(StockHolding(
            ticker='MSFT', name='Microsoft Corp.',
            quantity=5, avg_price=380.0,
            first_purchase_date=datetime(2024, 3, 1),
        ))
        db.commit()
        print('Sample stocks inserted')
    else:
        print('Stocks already exist')
"
```

- [ ] **Step 4: Commit**

```bash
git add backend/database.py
git commit -m "feat(db): add StockHolding model for US stock positions"
```

---

### Task 3: 주식 서비스 레이어 (`services/stock.py`)

**Files:**
- Create: `backend/services/stock.py`

- [ ] **Step 1: stock.py 서비스 작성**

`backend/services/stock.py` 생성:

```python
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
    """종목 상세 정보 조회 (캐시 15분).

    Returns: 밸류에이션, 수익성, 배당, 시장 데이터, 애널리스트 컨센서스.
    """
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
        # 기본 정보
        "symbol": info.get("symbol"),
        "name": info.get("shortName") or info.get("longName"),
        "currency": info.get("currency", "USD"),
        "exchange": info.get("exchange"),

        # 가격
        "current_price": current_price,
        "previous_close": previous_close,
        "price_change": price_change,
        "price_change_pct": price_change_pct,
        "post_market_price": info.get("postMarketPrice"),
        "post_market_change_pct": info.get("postMarketChangePercent"),

        # KRW 환산
        "current_price_krw": current_price * usd_krw if current_price and usd_krw else None,
        "usd_krw": usd_krw,

        # 밸류에이션
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "price_to_sales": info.get("priceToSalesTrailing12Months"),
        "ev_to_ebitda": info.get("enterpriseToEbitda"),

        # 수익성 / 배당
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "dividend_yield": info.get("dividendYield"),
        "dividend_rate": info.get("dividendRate"),
        "ex_dividend_date": _ts_to_str(info.get("exDividendDate")),

        # 시장 데이터
        "market_cap": info.get("marketCap"),
        "volume": info.get("volume"),
        "average_volume": info.get("averageVolume"),
        "day_low": info.get("dayLow"),
        "day_high": info.get("dayHigh"),
        "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),

        # 애널리스트
        "target_mean_price": info.get("targetMeanPrice"),
        "target_low_price": info.get("targetLowPrice"),
        "target_high_price": info.get("targetHighPrice"),
        "recommendation_key": info.get("recommendationKey"),
        "number_of_analysts": info.get("numberOfAnalystOpinions"),

        # 어닝
        "earnings_dates": _get_next_earnings(t),

        # 링크
        "website": info.get("website"),
        "logo_url": info.get("logo_url"),
    }

    _detail_cache[ticker] = {"data": data, "fetched_at": now}
    return data


def fetch_stock_price_history(ticker: str, days: int = 30) -> Dict[str, Any]:
    """주식 가격 히스토리 (차트용).

    Returns: {"ticker": str, "timestamps": [str], "prices": [float]}
    """
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
    """보유 주식의 다가오는 어닝 날짜 목록.

    Returns: [{"ticker": str, "name": str, "earnings_date": str, "days_until": int}]
    캐시 TTL 6시간.
    """
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
            time.sleep(0.1)  # yfinance 레이트 리밋 방지
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
        # yfinance calendar는 dict 또는 DataFrame
        if isinstance(cal, dict):
            dates = cal.get("Earnings Date", [])
            if isinstance(dates, list):
                return [d.strftime("%Y-%m-%d") if hasattr(d, "strftime") else str(d) for d in dates]
        else:
            # DataFrame
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
```

- [ ] **Step 2: import 확인**

Run: `cd backend && source venv/bin/activate && python -c "from services.stock import get_usd_krw; print('USD/KRW:', get_usd_krw())"`
Expected: 환율 숫자 출력 (예: `USD/KRW: 1342.5`)

- [ ] **Step 3: 상세 조회 확인**

Run: `cd backend && source venv/bin/activate && python -c "from services.stock import fetch_stock_detail; d = fetch_stock_detail('AAPL'); print(d['name'], d['current_price'], d['trailing_pe'])"`
Expected: `Apple Inc. <가격> <PER>` 형태 출력

- [ ] **Step 4: Commit**

```bash
git add backend/services/stock.py
git commit -m "feat(services): add stock data service with yfinance wrapper"
```

---

### Task 4: 주식 라우터 (`routers/stock.py`)

**Files:**
- Create: `backend/routers/stock.py`

- [ ] **Step 1: stock.py 라우터 작성**

`backend/routers/stock.py` 생성:

```python
"""주식 상세 정보 라우터 — yfinance 기반."""
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from database import Session, StockHolding, engine
from services.stock import fetch_earnings_calendar, fetch_stock_detail, fetch_stock_price_history

router = APIRouter(prefix="/api/stock")


@router.get("/{ticker}")
def get_stock_detail(ticker: str) -> Dict[str, Any]:
    """티커 기준 주식 상세 정보 반환."""
    try:
        return fetch_stock_detail(ticker.upper())
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"주식 데이터 조회 실패: {e}")


@router.get("/{ticker}/price-history")
def get_stock_price_history(ticker: str, days: int = 30) -> Dict[str, Any]:
    """주식 가격 히스토리 (차트용)."""
    data = fetch_stock_price_history(ticker.upper(), days)
    if not data["timestamps"]:
        raise HTTPException(status_code=503, detail="가격 데이터 조회 실패")
    return data


@router.get("")
def get_earnings_calendar() -> Dict[str, Any]:
    """보유 주식 어닝 캘린더."""
    with Session(engine) as db:
        holdings = db.query(StockHolding).filter(StockHolding.is_active == True).all()

    if not holdings:
        return {"earnings": []}

    tickers = [h.ticker for h in holdings]
    earnings = fetch_earnings_calendar(tickers)
    return {"earnings": earnings}
```

- [ ] **Step 2: main.py에 라우터 등록**

`backend/main.py`에서 import 추가:

```python
from routers.stock import router as stock_router
```

라우터 등록 줄 추가 (coin_router 줄 다음):

```python
app.include_router(stock_router,     dependencies=[Depends(require_auth)])   # /api/stock/* (인증 필요)
```

- [ ] **Step 3: 서버 시작 확인**

Run: `cd backend && source venv/bin/activate && uvicorn main:app --port 8000 &`

그 뒤 API 확인:
Run: `curl -s http://localhost:8000/health`
Expected: `{"status":"ok"}`

서버 종료:
Run: `kill %1`

- [ ] **Step 4: Commit**

```bash
git add backend/routers/stock.py backend/main.py
git commit -m "feat(api): add stock detail and earnings calendar endpoints"
```

---

### Task 5: 포트폴리오 동기화에 주식 포함

**Files:**
- Modify: `backend/scheduler.py:125-258`
- Modify: `backend/routers/portfolio.py:10-22`

- [ ] **Step 1: scheduler.py에 주식 동기화 추가**

`backend/scheduler.py` 상단 import에 추가:

```python
from database import AssetSnapshot, ManualAsset, PortfolioSnapshot, Session, StockHolding, engine
from services.stock import get_usd_krw
```

`sync_portfolio()` 함수 안에서, 수동 자산 병합 블록(`if manual_assets:` ~ 끝) 다음에 주식 병합 블록 추가:

```python
    # 주식 보유 자산 현재가 조회 후 병합
    with Session(engine) as db:
        stock_holdings = db.query(StockHolding).filter(StockHolding.is_active == True).all()

    if stock_holdings:
        usd_krw = get_usd_krw()
        if usd_krw:
            for s in stock_holdings:
                try:
                    import yfinance as yf
                    t = yf.Ticker(s.ticker)
                    info = t.info
                    cur_price_usd = info.get("currentPrice") or info.get("regularMarketPrice")
                    if cur_price_usd is None:
                        continue
                    cur_price_krw = cur_price_usd * usd_krw
                    avg_price_krw = s.avg_price * usd_krw
                    previous_close = info.get("previousClose")
                    signed_change_price = 0.0
                    signed_change_rate = 0.0
                    if previous_close and previous_close > 0:
                        signed_change_price = (cur_price_usd - previous_close) * usd_krw
                        signed_change_rate = (cur_price_usd - previous_close) / previous_close
                    raw_assets.append({
                        "name": s.name,
                        "ticker": s.ticker,
                        "quantity": s.quantity,
                        "avg_price": avg_price_krw,
                        "current_price": cur_price_krw,
                        "first_purchase_date": s.first_purchase_date,
                        "asset_type": "stock",
                        "signed_change_price": signed_change_price,
                        "signed_change_rate": signed_change_rate,
                    })
                except Exception as e:
                    print(f"[Sync] 주식 {s.ticker} 조회 실패: {e}")
```

- [ ] **Step 2: AssetOut에 currency 필드 추가**

`backend/routers/portfolio.py`의 `AssetOut` 클래스에 필드 추가:

```python
    currency: str = "KRW"
```

- [ ] **Step 3: 서버 재시작 후 포트폴리오 확인**

Run: `cd backend && source venv/bin/activate && python -c "
from scheduler import sync_portfolio, get_portfolio_cache
from database import init_db
init_db()
sync_portfolio()
cache = get_portfolio_cache()
for a in cache.get('assets', []):
    print(f'{a[\"ticker\"]:15} {a[\"asset_type\"]:8} {a[\"current_price\"]:>15,.0f} KRW')
"`
Expected: 코인 + 주식 자산이 모두 출력됨

- [ ] **Step 4: Commit**

```bash
git add backend/scheduler.py backend/routers/portfolio.py
git commit -m "feat(scheduler): include US stock holdings in portfolio sync"
```

---

### Task 6: 통합 상세 페이지 — 주식 섹션 추가

**Files:**
- Modify: `frontend/detail.html`

- [ ] **Step 1: URL 파라미터 분기 추가**

`frontend/detail.html`의 `// ── State` 섹션 (~line 264)을 다음으로 교체:

```javascript
// ── State ──────────────────────────────────────────────────────────────────────
const params = new URLSearchParams(location.search);
const ticker = params.get('ticker') || '';
const assetType = params.get('type') || 'coin';  // 'coin' | 'stock'
let priceChart = null;
let currentDays = 30;
```

- [ ] **Step 2: 주식 헤더 렌더 함수 추가**

`renderLinks()` 함수 뒤에 주식용 렌더 함수들 추가:

```javascript
function renderStockHeader(detail) {
    const wrap = document.getElementById('coin-logo-wrap');
    if (detail.logo_url) {
        wrap.innerHTML = `<img src="${detail.logo_url}" class="coin-logo" alt="${detail.symbol}">`;
    } else {
        wrap.innerHTML = `<div class="coin-logo-placeholder">${(detail.symbol || '?').slice(0,3)}</div>`;
    }

    document.getElementById('coin-name').textContent = detail.name ?? '—';
    document.getElementById('coin-symbol').textContent = detail.symbol ?? '';
    document.getElementById('nav-title').textContent = detail.name ?? ticker;
    document.title = `${detail.name ?? ticker} — My Portfolio`;

    // 현재가 (USD)
    const USD = v => v == null ? '—' : `$${v.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    document.getElementById('current-price').textContent = USD(detail.current_price);

    const pct = detail.price_change_pct;
    const badge = document.getElementById('change-24h-badge');
    badge.textContent = PCT(pct);
    badge.className = `badge-change ${pct != null && pct >= 0 ? 'badge-up' : 'badge-down'}`;

    // 시간외 가격
    const periodWrap = document.getElementById('period-changes');
    periodWrap.innerHTML = '';
    if (detail.post_market_price) {
        const span = document.createElement('span');
        span.className = 'badge-change badge-up';
        span.style.background = 'rgba(100,116,139,.1)';
        span.style.color = '#64748b';
        span.textContent = `시간외 ${USD(detail.post_market_price)}`;
        periodWrap.appendChild(span);
    }
    if (detail.current_price_krw) {
        const span = document.createElement('span');
        span.className = 'badge-change';
        span.style.background = 'rgba(100,116,139,.1)';
        span.style.color = '#64748b';
        span.textContent = `≈ ${KRW(detail.current_price_krw)}`;
        periodWrap.appendChild(span);
    }
}
```

- [ ] **Step 3: 주식 시장 데이터 렌더 함수 추가**

```javascript
function renderStockMarketGrid(detail) {
    const USD = v => v == null ? '—' : `$${v.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    const BIGNUM = v => {
        if (v == null) return '—';
        if (v >= 1e12) return `$${(v/1e12).toFixed(2)}T`;
        if (v >= 1e9) return `$${(v/1e9).toFixed(2)}B`;
        if (v >= 1e6) return `$${(v/1e6).toFixed(2)}M`;
        return `$${v.toLocaleString()}`;
    };
    const PCTFMT = v => v == null ? '—' : `${(v * 100).toFixed(2)}%`;
    const RATIO = v => v == null ? '—' : v.toFixed(2);

    // Range bar helper
    const rangeBar = (low, high, current) => {
        if (low == null || high == null || current == null) return '';
        const pct = high > low ? ((current - low) / (high - low) * 100) : 50;
        return `<div style="height:6px;border-radius:3px;background:#e2e8f0;margin-top:4px;position:relative;">
            <div style="height:100%;border-radius:3px;background:linear-gradient(90deg,#dc2626,#f59e0b,#16a34a);width:100%;opacity:.3;"></div>
            <div style="position:absolute;top:-2px;left:${Math.min(Math.max(pct,2),98)}%;width:10px;height:10px;border-radius:50%;background:#1e293b;transform:translateX(-50%);"></div>
        </div>`;
    };

    const sections = [
        { title: '밸류에이션', items: [
            { label: 'PER (TTM)', value: RATIO(detail.trailing_pe) },
            { label: 'Forward PER', value: RATIO(detail.forward_pe) },
            { label: 'PBR', value: RATIO(detail.price_to_book) },
            { label: 'PSR', value: RATIO(detail.price_to_sales) },
            { label: 'EV/EBITDA', value: RATIO(detail.ev_to_ebitda) },
        ]},
        { title: '수익성 / 배당', items: [
            { label: 'ROE', value: PCTFMT(detail.roe) },
            { label: 'ROA', value: PCTFMT(detail.roa) },
            { label: '배당수익률', value: PCTFMT(detail.dividend_yield) },
            { label: '연간 배당금', value: USD(detail.dividend_rate) },
            { label: '배당일', value: detail.ex_dividend_date ?? '—' },
        ]},
        { title: '시장 데이터', items: [
            { label: '시가총액', value: BIGNUM(detail.market_cap) },
            { label: '거래량', value: detail.volume ? detail.volume.toLocaleString() : '—' },
            { label: '평균 거래량', value: detail.average_volume ? detail.average_volume.toLocaleString() : '—' },
            { label: 'Day Range', value: `${USD(detail.day_low)} — ${USD(detail.day_high)}`, extra: rangeBar(detail.day_low, detail.day_high, detail.current_price) },
            { label: '52주 Range', value: `${USD(detail.fifty_two_week_low)} — ${USD(detail.fifty_two_week_high)}`, extra: rangeBar(detail.fifty_two_week_low, detail.fifty_two_week_high, detail.current_price) },
        ]},
        { title: '애널리스트 컨센서스', items: [
            { label: '추천', value: (detail.recommendation_key ?? '—').toUpperCase() },
            { label: '목표가 (평균)', value: USD(detail.target_mean_price) },
            { label: '목표가 범위', value: `${USD(detail.target_low_price)} — ${USD(detail.target_high_price)}` },
            { label: '애널리스트 수', value: detail.number_of_analysts ?? '—' },
        ]},
    ];

    const grid = document.getElementById('market-grid');
    grid.innerHTML = '';
    grid.className = '';  // 기존 row g-2 제거

    sections.forEach(sec => {
        const sectionEl = document.createElement('div');
        sectionEl.className = 'mb-4';
        sectionEl.innerHTML = `<div class="section-title">${sec.title}</div>
            <div class="row g-2">${sec.items.map(i => `
                <div class="col-6 col-md-4 col-lg-6 col-xl-4">
                    <div class="stat-cell">
                        <div class="stat-label">${i.label}</div>
                        <div class="stat-value">${i.value}</div>
                        ${i.extra || ''}
                    </div>
                </div>`).join('')}
            </div>`;
        grid.appendChild(sectionEl);
    });
}
```

- [ ] **Step 4: 주식 가격 차트 함수 추가**

```javascript
async function renderStockPriceChart(days) {
    try {
        const data = await apiFetch(`/api/stock/${encodeURIComponent(ticker)}/price-history?days=${days}`);
        if (!data.timestamps?.length) return;

        const axisFormat = days <= 90
            ? d => `${d.getMonth()+1}/${d.getDate()}`
            : d => `${d.getFullYear()}/${d.getMonth()+1}`;

        const labels = data.timestamps.map(t => {
            const [y, m, d] = t.split('-').map(Number);
            return axisFormat(new Date(y, m-1, d));
        });

        const firstPrice = data.prices[0] || 1;
        const lastPrice  = data.prices[data.prices.length - 1] ?? firstPrice;
        const isUp = lastPrice >= firstPrice;
        const lineColor = isUp ? '#16a34a' : '#dc2626';
        const bgColor   = isUp ? 'rgba(22,163,74,.08)' : 'rgba(220,38,38,.08)';

        const tooltipCb = {
            title: ctx => data.timestamps[ctx[0].dataIndex],
            label: ctx => ` $${ctx.parsed.y.toLocaleString('en-US', {minimumFractionDigits:2, maximumFractionDigits:2})}`,
        };
        const yTickCb = v => {
            if (v >= 1e6) return `$${(v/1e6).toFixed(0)}M`;
            if (v >= 1e3) return `$${(v/1e3).toFixed(0)}K`;
            return `$${v}`;
        };

        if (!priceChart) {
            priceChart = new Chart(document.getElementById('price-chart'), {
                type: 'line',
                data: { labels, datasets: [{
                    data: data.prices, borderColor: lineColor, backgroundColor: bgColor,
                    fill: true, tension: 0.3, pointRadius: 0, pointHoverRadius: 4, borderWidth: 2,
                }]},
                options: {
                    interaction: { mode: 'index', intersect: false },
                    plugins: { legend: { display: false }, tooltip: { callbacks: tooltipCb } },
                    scales: {
                        x: { ticks: { maxTicksLimit: days <= 90 ? 10 : 8, font: { size: 10 }, maxRotation: 0 }, grid: { display: false } },
                        y: { ticks: { callback: yTickCb, font: { size: 10 } }, grid: { color: '#f1f5f9' } },
                    },
                    maintainAspectRatio: false,
                }
            });
        } else {
            priceChart.options.scales.x.ticks.maxTicksLimit = days <= 90 ? 10 : 8;
            priceChart.data.labels = labels;
            priceChart.data.datasets[0].data = data.prices;
            priceChart.data.datasets[0].borderColor = lineColor;
            priceChart.data.datasets[0].backgroundColor = bgColor;
            priceChart.options.plugins.tooltip.callbacks = tooltipCb;
            priceChart.options.scales.y.ticks.callback = yTickCb;
            priceChart.update();
        }
    } catch(e) {
        console.error('stock price chart error:', e);
    }
}
```

- [ ] **Step 5: loadDetail() 분기 처리**

기존 `loadDetail()` 함수를 다음으로 교체:

```javascript
async function loadDetail() {
    if (!ticker) { window.location.href = '/'; return; }

    try {
        if (assetType === 'stock') {
            const [detail, portfolio] = await Promise.all([
                apiFetch(`/api/stock/${encodeURIComponent(ticker)}`),
                apiFetch('/api/portfolio'),
            ]);

            renderStockHeader(detail);
            renderStockMarketGrid(detail);

            // 링크
            if (detail.website) {
                document.getElementById('links-section').classList.remove('d-none');
                document.getElementById('links-wrap').innerHTML =
                    `<a href="${detail.website}" target="_blank" rel="noopener"
                        class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1">
                        <i class="bi bi-globe"></i> 공식 사이트
                     </a>`;
            }

            const myAsset = (portfolio.assets || []).find(a => a.ticker === ticker);
            renderHolding(myAsset, portfolio.total_value);

            await renderStockPriceChart(currentDays);
        } else {
            // 기존 코인 로직
            const [detail, portfolio] = await Promise.all([
                apiFetch(`/api/coin/${encodeURIComponent(ticker)}`),
                apiFetch('/api/portfolio'),
            ]);

            renderHeader(detail);
            renderMarketGrid(detail);
            renderLinks(detail);

            const myAsset = (portfolio.assets || []).find(a => a.ticker === ticker);
            renderHolding(myAsset, portfolio.total_value);

            await renderPriceChart(currentDays);
        }

        document.getElementById('loading-overlay').style.display = 'none';
        document.getElementById('main-content').style.display = '';
    } catch(e) {
        if (e.message === 'Unauthenticated' || e.message === 'Unauthorized') return;
        document.getElementById('loading-overlay').style.display = 'none';
        document.getElementById('main-content').style.display = '';
        const banner = document.getElementById('error-banner');
        banner.textContent = '데이터 로딩 실패: ' + e.message;
        banner.classList.remove('d-none');
    }
}
```

- [ ] **Step 6: 차트 기간 버튼 분기**

기존 차트 기간 버튼 이벤트 리스너(~line 505-512)를 교체:

```javascript
document.getElementById('chart-period-btns').addEventListener('click', async e => {
    const btn = e.target.closest('button[data-days]');
    if (!btn) return;
    document.querySelectorAll('#chart-period-btns button').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    currentDays = +btn.dataset.days;
    if (assetType === 'stock') {
        await renderStockPriceChart(currentDays);
    } else {
        await renderPriceChart(currentDays);
    }
});
```

- [ ] **Step 7: 브라우저에서 주식 상세 페이지 확인**

서버 시작 후 브라우저에서 `http://localhost:8000/detail.html?type=stock&ticker=AAPL` 접속.

확인 사항:
- 종목명, 현재가 (USD), 등락률 표시
- KRW 환산 뱃지 표시
- 밸류에이션 (PER/PBR/PSR/EV-EBITDA) 섹션
- 수익성/배당 섹션
- 시장 데이터 (Day Range, 52W Range 미니바 포함)
- 애널리스트 컨센서스 섹션
- 가격 차트 (기간 변경 동작)

- [ ] **Step 8: Commit**

```bash
git add frontend/detail.html
git commit -m "feat(frontend): add stock detail view to unified detail page"
```

---

### Task 7: 대시보드 보유현황 테이블에 주식 행 클릭 링크 추가

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: 보유현황 테이블 행 링크 수정**

`frontend/index.html` ~line 632-633에서 기존 코드:

```javascript
tr.addEventListener('click', () => {
    window.location.href = `/detail.html?ticker=${encodeURIComponent(a.ticker)}`;
});
```

이것을 자산 타입에 따라 분기하도록 수정:

```javascript
tr.addEventListener('click', () => {
    const type = a.asset_type === 'stock' ? 'stock' : 'coin';
    window.location.href = `/detail.html?type=${type}&ticker=${encodeURIComponent(a.ticker)}`;
});
```

- [ ] **Step 2: 주식 자산에 타입 뱃지 추가**

~line 636-638의 종목 셀 코드:

```javascript
<td>
    <div class="fw-semibold">${a.name}</div>
    <div class="text-muted" style="font-size:.72rem;">${a.ticker}</div>
</td>
```

이것을 다음으로 수정:

```javascript
<td>
    <div class="fw-semibold">${a.name}${a.asset_type === 'stock' ? ' <span class="badge bg-primary-subtle text-primary" style="font-size:.6rem;">US</span>' : ''}</div>
    <div class="text-muted" style="font-size:.72rem;">${a.ticker}</div>
</td>
```

- [ ] **Step 3: 브라우저 확인**

대시보드에서:
- 코인 행: 기존과 동일하게 코인 상세로 이동
- 주식 행: "US" 뱃지 표시, 클릭 시 주식 상세 페이지로 이동

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat(frontend): link stock rows to unified detail page with type badge"
```

---

### Task 8: 대시보드 어닝 캘린더 섹션

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: HTML 섹션 추가**

`frontend/index.html`에서 보유현황 테이블(`<div id="holdings">`) 뒤, 자산배분(`<div id="allocation">`) 앞에 어닝 캘린더 섹션 추가:

```html
    <!-- ③-2 어닝 캘린더 -->
    <div id="earnings" class="section-card bg-white mb-4 d-none">
        <div class="p-4 pb-0">
            <div class="section-title">다가오는 실적 발표</div>
        </div>
        <div class="table-responsive">
            <table class="table holdings-table mb-0">
                <thead>
                    <tr>
                        <th>종목</th>
                        <th class="num">실적 발표일</th>
                        <th class="num">D-Day</th>
                    </tr>
                </thead>
                <tbody id="earnings-tbody"></tbody>
            </table>
        </div>
    </div>
```

- [ ] **Step 2: JS 렌더 함수 추가**

대시보드 JS 영역에 어닝 캘린더 렌더 함수 추가:

```javascript
async function loadEarningsCalendar() {
    try {
        const data = await apiFetch('/api/stock');
        const earnings = data.earnings || [];
        if (!earnings.length) return;

        const tbody = document.getElementById('earnings-tbody');
        tbody.innerHTML = earnings.map(e => {
            const isUrgent = e.days_until <= 7;
            const urgentCls = isUrgent ? 'fw-bold' : '';
            const dday = e.days_until === 0 ? '<span class="badge bg-danger">오늘</span>'
                       : e.days_until <= 7 ? `<span class="badge bg-warning text-dark">D-${e.days_until}</span>`
                       : `D-${e.days_until}`;
            return `<tr class="${urgentCls}">
                <td>
                    <a href="detail.html?type=stock&ticker=${e.ticker}" class="text-decoration-none text-dark">
                        <span class="fw-semibold">${e.ticker}</span>
                        <span class="text-muted" style="font-size:.8rem;margin-left:.3rem;">${e.name}</span>
                    </a>
                </td>
                <td class="num">${e.earnings_date}</td>
                <td class="num">${dday}</td>
            </tr>`;
        }).join('');

        document.getElementById('earnings').classList.remove('d-none');
    } catch(e) {
        console.error('earnings calendar error:', e);
    }
}
```

- [ ] **Step 3: loadDashboard에서 어닝 캘린더 호출**

대시보드의 메인 로드 함수(데이터 로드 후)에 `loadEarningsCalendar()` 호출 추가. 이 호출은 포트폴리오 로드와 병렬로 실행 (별도 `await` 없이):

```javascript
loadEarningsCalendar();  // 비동기 — 메인 로딩 블로킹 안함
```

- [ ] **Step 4: 사이드바에 어닝 캘린더 링크 추가**

사이드바 "대시보드" 그룹에 어닝 캘린더 링크 추가:

```html
<a href="#earnings" class="sidebar-link" data-nav="earnings">실적 발표</a>
```

`리스크 지표` 링크 뒤에 삽입.

- [ ] **Step 5: 브라우저 확인**

대시보드에서:
- 보유현황 아래에 "다가오는 실적 발표" 섹션 표시
- D-7 이내는 뱃지로 강조
- 종목 클릭 시 주식 상세로 이동
- 보유 주식이 없거나 어닝이 없으면 섹션 숨김

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html
git commit -m "feat(frontend): add earnings calendar section to dashboard"
```

---

### Task 9: 최종 통합 테스트 및 정리

**Files:**
- All modified files

- [ ] **Step 1: 서버 시작**

Run: `cd backend && source venv/bin/activate && uvicorn main:app --port 8000`

- [ ] **Step 2: 전체 기능 확인 체크리스트**

브라우저에서 `http://localhost:8000` 접속 후:

1. 대시보드 로드 — 코인 + 주식 자산 모두 보유현황 테이블에 표시
2. 주식 행에 "US" 뱃지 표시
3. 주식 행 클릭 → 주식 상세 페이지 (`detail.html?type=stock&ticker=AAPL`)
4. 주식 상세: 헤더(종목명, USD 가격, KRW 환산), 밸류에이션, 수익성/배당, 시장 데이터(Range 미니바), 애널리스트, 가격 차트
5. 코인 행 클릭 → 코인 상세 페이지 (기존과 동일하게 동작)
6. 어닝 캘린더 섹션 표시 (보유 주식의 실적 발표일)
7. 사이드바 "실적 발표" 링크 동작

- [ ] **Step 3: phase2-detail.md 요구사항 체크 업데이트**

`docs/requirements/phase2-detail.md` 상단에 구현 완료 기준일 추가:

```markdown
> 구현 완료 기준일: 2026-04-XX (실제 완료일로 교체)
```

- [ ] **Step 4: Commit**

```bash
git add docs/requirements/phase2-detail.md
git commit -m "docs: mark Phase 2 implementation as complete"
```
