# Phase 3 서브프로젝트 B: 뉴스 수집기 1차 (무료 6개) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** API 키 없이 사용 가능한 무료 소스 6개의 뉴스 수집기를 구현하고, `collect_all()`로 일괄 실행 가능하게 한다.

**Architecture:** 각 수집기는 `BaseCollector`를 상속하고 `@register`로 등록. RSS 수집기는 `feedparser`+`httpx`, API 수집기는 `httpx`만 사용. 각 파일은 독립적이며 하나의 소스만 담당한다.

**Tech Stack:** Python 3.9, httpx, feedparser, SQLAlchemy (StockHolding 조회)

**Spec:** `docs/superpowers/specs/2026-04-12-phase3-subproject-b-collectors.md`

---

### Task 1: 의존성 추가 (feedparser, httpx)

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: requirements.txt에 feedparser, httpx 추가**

`backend/requirements.txt` 끝에 두 줄 추가:

```
feedparser
httpx
```

- [ ] **Step 2: 설치**

Run: `cd backend && pip install feedparser httpx`

- [ ] **Step 3: 커밋**

```bash
git add backend/requirements.txt
git commit -m "chore: add feedparser and httpx dependencies for news collectors"
```

---

### Task 2: CoinDesk RSS 수집기

**Files:**
- Create: `backend/services/collectors/coindesk.py`

- [ ] **Step 1: coindesk.py 작성**

`backend/services/collectors/coindesk.py`를 다음 내용으로 생성한다:

```python
"""CoinDesk RSS 뉴스 수집기."""

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List

import feedparser
import httpx

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

RSS_URL = "https://www.coindesk.com/arc/outboundfeeds/rss/"


@register
class CoinDeskCollector(BaseCollector):
    name = "coindesk"

    async def collect(self) -> List[RawNewsItem]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(RSS_URL)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        items: List[RawNewsItem] = []

        for entry in feed.entries:
            published = self._parse_date(entry)
            if published and published < cutoff:
                continue
            items.append(RawNewsItem(
                source=self.name,
                title=entry.get("title", ""),
                content=entry.get("summary", ""),
                url=entry.get("link", ""),
                published_at=published,
            ))

        return items

    @staticmethod
    def _parse_date(entry) -> datetime:
        """RSS 엔트리에서 발행 시각을 파싱한다."""
        date_str = entry.get("published") or entry.get("updated")
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.collectors.coindesk import CoinDeskCollector; print(CoinDeskCollector.name)"`

Expected: `coindesk`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/collectors/coindesk.py
git commit -m "feat: add CoinDesk RSS news collector"
```

---

### Task 3: Cointelegraph RSS 수집기

**Files:**
- Create: `backend/services/collectors/cointelegraph.py`

- [ ] **Step 1: cointelegraph.py 작성**

`backend/services/collectors/cointelegraph.py`를 다음 내용으로 생성한다:

```python
"""Cointelegraph RSS 뉴스 수집기."""

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List

import feedparser
import httpx

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

RSS_URL = "https://cointelegraph.com/rss"


@register
class CointelegraphCollector(BaseCollector):
    name = "cointelegraph"

    async def collect(self) -> List[RawNewsItem]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(RSS_URL)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        items: List[RawNewsItem] = []

        for entry in feed.entries:
            published = self._parse_date(entry)
            if published and published < cutoff:
                continue
            items.append(RawNewsItem(
                source=self.name,
                title=entry.get("title", ""),
                content=entry.get("summary", ""),
                url=entry.get("link", ""),
                published_at=published,
            ))

        return items

    @staticmethod
    def _parse_date(entry) -> datetime:
        """RSS 엔트리에서 발행 시각을 파싱한다."""
        date_str = entry.get("published") or entry.get("updated")
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.collectors.cointelegraph import CointelegraphCollector; print(CointelegraphCollector.name)"`

Expected: `cointelegraph`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/collectors/cointelegraph.py
git commit -m "feat: add Cointelegraph RSS news collector"
```

---

### Task 4: Yahoo Finance RSS 수집기

**Files:**
- Create: `backend/services/collectors/yahoo_finance.py`

- [ ] **Step 1: yahoo_finance.py 작성**

`backend/services/collectors/yahoo_finance.py`를 다음 내용으로 생성한다:

```python
"""Yahoo Finance RSS 뉴스 수집기 — 보유 주식 종목별 뉴스."""

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List

import feedparser
import httpx
from sqlalchemy.orm import Session

from database import StockHolding, engine
from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

RSS_URL_TEMPLATE = "https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}"


@register
class YahooFinanceCollector(BaseCollector):
    name = "yahoo_finance"

    async def collect(self) -> List[RawNewsItem]:
        tickers = self._get_stock_tickers()
        if not tickers:
            logger.info("[yahoo_finance] no stock holdings found, skipping")
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        items: List[RawNewsItem] = []

        async with httpx.AsyncClient(timeout=15) as client:
            for ticker in tickers:
                try:
                    url = RSS_URL_TEMPLATE.format(ticker=ticker)
                    resp = await client.get(url)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)

                    for entry in feed.entries:
                        published = self._parse_date(entry)
                        if published and published < cutoff:
                            continue
                        items.append(RawNewsItem(
                            source=self.name,
                            title=f"[{ticker}] {entry.get('title', '')}",
                            content=entry.get("summary", ""),
                            url=entry.get("link", ""),
                            published_at=published,
                        ))
                except Exception as e:
                    logger.warning(f"[yahoo_finance] failed for {ticker}: {e}")

        return items

    @staticmethod
    def _get_stock_tickers() -> List[str]:
        """DB에서 활성 주식 종목 티커 목록을 조회한다."""
        with Session(engine) as session:
            holdings = session.query(StockHolding.ticker).filter(
                StockHolding.is_active == True
            ).all()
            return [h.ticker for h in holdings]

    @staticmethod
    def _parse_date(entry) -> datetime:
        """RSS 엔트리에서 발행 시각을 파싱한다."""
        date_str = entry.get("published") or entry.get("updated")
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.collectors.yahoo_finance import YahooFinanceCollector; print(YahooFinanceCollector.name)"`

Expected: `yahoo_finance`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/collectors/yahoo_finance.py
git commit -m "feat: add Yahoo Finance RSS news collector"
```

---

### Task 5: CoinGecko API 수집기

**Files:**
- Create: `backend/services/collectors/coingecko.py`

- [ ] **Step 1: coingecko.py 작성**

`backend/services/collectors/coingecko.py`를 다음 내용으로 생성한다:

```python
"""CoinGecko API 수집기 — 트렌딩 코인 데이터."""

import logging
from datetime import datetime, timezone
from typing import List

import httpx

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"


@register
class CoinGeckoCollector(BaseCollector):
    name = "coingecko"

    async def collect(self) -> List[RawNewsItem]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(TRENDING_URL)
            resp.raise_for_status()

        data = resp.json()
        coins = data.get("coins", [])[:7]
        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        for coin_wrap in coins:
            coin = coin_wrap.get("item", {})
            name = coin.get("name", "Unknown")
            symbol = coin.get("symbol", "")
            market_cap_rank = coin.get("market_cap_rank", "N/A")
            price_change_24h = coin.get("data", {}).get("price_change_percentage_24h", {})
            usd_change = price_change_24h.get("usd", 0) if isinstance(price_change_24h, dict) else 0

            sign = "+" if usd_change >= 0 else ""
            title = f"[Trending] {name} ({symbol}) — 24h {sign}{usd_change:.1f}%"
            content = f"Market cap rank: #{market_cap_rank}. 24h price change: {sign}{usd_change:.1f}%"

            items.append(RawNewsItem(
                source=self.name,
                title=title,
                content=content,
                url=f"https://www.coingecko.com/en/coins/{coin.get('id', '')}",
                published_at=now,
            ))

        return items
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.collectors.coingecko import CoinGeckoCollector; print(CoinGeckoCollector.name)"`

Expected: `coingecko`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/collectors/coingecko.py
git commit -m "feat: add CoinGecko trending coins collector"
```

---

### Task 6: SEC EDGAR API 수집기

**Files:**
- Create: `backend/services/collectors/sec_edgar.py`

- [ ] **Step 1: sec_edgar.py 작성**

`backend/services/collectors/sec_edgar.py`를 다음 내용으로 생성한다:

```python
"""SEC EDGAR 수집기 — 보유 주식 공시/내부자거래."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List

import httpx
from sqlalchemy.orm import Session

from database import StockHolding, engine
from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

SEARCH_URL = "https://efts.sec.gov/LATEST/search-index"
USER_AGENT = "StockPortfolio/1.0 (contact@example.com)"


@register
class SecEdgarCollector(BaseCollector):
    name = "sec_edgar"

    async def collect(self) -> List[RawNewsItem]:
        tickers = self._get_stock_tickers()
        if not tickers:
            logger.info("[sec_edgar] no stock holdings found, skipping")
            return []

        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")
        items: List[RawNewsItem] = []

        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for ticker in tickers:
                try:
                    resp = await client.get(SEARCH_URL, params={
                        "q": f'"{ticker}"',
                        "dateRange": "custom",
                        "startdt": yesterday,
                        "enddt": today,
                        "forms": "4,8-K,10-Q,10-K",
                    })
                    resp.raise_for_status()
                    data = resp.json()

                    for hit in data.get("hits", {}).get("hits", [])[:5]:
                        source_data = hit.get("_source", {})
                        form_type = source_data.get("forms", [""])[0] if source_data.get("forms") else "Filing"
                        company = source_data.get("display_names", [""])[0] if source_data.get("display_names") else ticker
                        file_date = source_data.get("file_date", "")
                        file_num = source_data.get("file_num", [""])[0] if source_data.get("file_num") else ""

                        filing_url = f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&company={ticker}&type={form_type}&dateb=&owner=include&count=10"

                        items.append(RawNewsItem(
                            source=self.name,
                            title=f"[{ticker}] SEC {form_type}: {company}",
                            content=f"Form {form_type} filed on {file_date}. File number: {file_num}",
                            url=filing_url,
                            published_at=datetime.now(timezone.utc),
                        ))
                except Exception as e:
                    logger.warning(f"[sec_edgar] failed for {ticker}: {e}")

        return items

    @staticmethod
    def _get_stock_tickers() -> List[str]:
        """DB에서 활성 주식 종목 티커 목록을 조회한다."""
        with Session(engine) as session:
            holdings = session.query(StockHolding.ticker).filter(
                StockHolding.is_active == True
            ).all()
            return [h.ticker for h in holdings]
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.collectors.sec_edgar import SecEdgarCollector; print(SecEdgarCollector.name)"`

Expected: `sec_edgar`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/collectors/sec_edgar.py
git commit -m "feat: add SEC EDGAR filings collector"
```

---

### Task 7: Fear & Greed Index 수집기

**Files:**
- Create: `backend/services/collectors/fear_greed.py`

- [ ] **Step 1: fear_greed.py 작성**

`backend/services/collectors/fear_greed.py`를 다음 내용으로 생성한다:

```python
"""Fear & Greed Index 수집기 — 주식(CNN) + 크립토(Alternative.me) 시장 심리."""

import logging
from datetime import datetime, timezone
from typing import List

import httpx

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
CRYPTO_URL = "https://api.alternative.me/fng/?limit=1"


@register
class FearGreedCollector(BaseCollector):
    name = "fear_greed"

    async def collect(self) -> List[RawNewsItem]:
        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        # CNN Fear & Greed (주식)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(CNN_URL)
                resp.raise_for_status()
                data = resp.json()

            score = data.get("fear_and_greed", {}).get("score", None)
            rating = data.get("fear_and_greed", {}).get("rating", "")
            if score is not None:
                items.append(RawNewsItem(
                    source=self.name,
                    title=f"CNN Fear & Greed Index: {score:.0f} ({rating})",
                    content=f"Stock market sentiment: {rating}. Score: {score:.0f}/100.",
                    url="https://edition.cnn.com/markets/fear-and-greed",
                    published_at=now,
                ))
        except Exception as e:
            logger.warning(f"[fear_greed] CNN fetch failed: {e}")

        # Crypto Fear & Greed (Alternative.me)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(CRYPTO_URL)
                resp.raise_for_status()
                data = resp.json()

            fng_data = data.get("data", [{}])[0]
            value = fng_data.get("value", "")
            classification = fng_data.get("value_classification", "")
            if value:
                items.append(RawNewsItem(
                    source=self.name,
                    title=f"Crypto Fear & Greed Index: {value} ({classification})",
                    content=f"Crypto market sentiment: {classification}. Score: {value}/100.",
                    url="https://alternative.me/crypto/fear-and-greed-index/",
                    published_at=now,
                ))
        except Exception as e:
            logger.warning(f"[fear_greed] Crypto fetch failed: {e}")

        return items
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.collectors.fear_greed import FearGreedCollector; print(FearGreedCollector.name)"`

Expected: `fear_greed`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/collectors/fear_greed.py
git commit -m "feat: add Fear & Greed Index collector (CNN + crypto)"
```

---

### Task 8: 통합 테스트 — collect_all 실행

**Files:** 없음 (수동 확인)

- [ ] **Step 1: 모든 수집기 import 후 collect_all 실행**

`collect_all()`은 `COLLECTORS` 레지스트리에 등록된 수집기만 실행한다. 수집기 파일을 import해야 `@register`가 실행된다. 다음 스크립트로 전체 수집기를 테스트한다:

Run:
```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python3 -c "
import asyncio
import logging
logging.basicConfig(level=logging.INFO)

# 모든 수집기 import (register 실행)
import services.collectors.coindesk
import services.collectors.cointelegraph
import services.collectors.yahoo_finance
import services.collectors.coingecko
import services.collectors.sec_edgar
import services.collectors.fear_greed

from services.collectors import collect_all, COLLECTORS

print(f'Registered collectors: {[c.name for c in COLLECTORS]}')

async def main():
    items = await collect_all()
    print(f'Total collected: {len(items)} items')
    for item in items[:5]:
        print(f'  [{item.source}] {item.title[:60]}')

asyncio.run(main())
"
```

Expected: 등록된 수집기 6개 출력, 수집된 아이템 수 출력, 처음 5개 아이템 미리보기. 일부 소스가 네트워크 문제로 실패하더라도 다른 소스는 정상 수집되어야 한다.

- [ ] **Step 2: 에러가 있으면 수정 후 커밋**

문제가 있으면 해당 수집기를 수정하고 커밋한다.
