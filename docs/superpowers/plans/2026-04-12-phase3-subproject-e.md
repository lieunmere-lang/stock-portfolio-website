# Phase 3 서브프로젝트 E: 수집기 2차 (Google News + Investing.com) 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google News RSS 수집기와 Investing.com 경제캘린더 스크래핑 수집기를 추가한다.

**Architecture:** 기존 BaseCollector 플러그인 구조에 `@register`로 등록. scheduler.py의 `generate_news_report()`에 새 수집기 import 추가.

**Tech Stack:** Python 3.9, httpx, feedparser, BeautifulSoup4

**Spec:** `docs/superpowers/specs/2026-04-12-phase3-subproject-e-collectors2.md`

---

### Task 1: 의존성 추가 (beautifulsoup4)

**Files:**
- Modify: `backend/requirements.txt`

- [ ] **Step 1: requirements.txt에 beautifulsoup4 추가**

`backend/requirements.txt` 끝에 한 줄 추가:

```
beautifulsoup4
```

- [ ] **Step 2: 설치**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && pip install beautifulsoup4`

- [ ] **Step 3: 커밋**

```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
git add backend/requirements.txt
git commit -m "chore: add beautifulsoup4 dependency for web scraping collectors"
```

---

### Task 2: Google News RSS 수집기

**Files:**
- Create: `backend/services/collectors/google_news.py`

- [ ] **Step 1: google_news.py 작성**

`backend/services/collectors/google_news.py`를 다음 내용으로 생성한다:

```python
"""Google News RSS 수집기 — 보유 종목 키워드 검색 (안전망)."""

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List
from urllib.parse import quote

import feedparser
import httpx
from sqlalchemy.orm import Session

from database import ManualAsset, StockHolding, engine
from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

RSS_URL_TEMPLATE = "https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko"


@register
class GoogleNewsCollector(BaseCollector):
    name = "google_news"

    async def collect(self) -> List[RawNewsItem]:
        keywords = self._get_keywords()
        if not keywords:
            logger.info("[google_news] no keywords, skipping")
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        items: List[RawNewsItem] = []

        async with httpx.AsyncClient(timeout=15) as client:
            for keyword in keywords:
                try:
                    url = RSS_URL_TEMPLATE.format(keyword=quote(keyword))
                    resp = await client.get(url)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)

                    for entry in feed.entries[:5]:
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
                except Exception as e:
                    logger.warning(f"[google_news] failed for '{keyword}': {e}")

        return items

    @staticmethod
    def _get_keywords() -> List[str]:
        """DB에서 보유 종목의 이름과 티커를 키워드로 생성한다."""
        keywords = []
        with Session(engine) as session:
            for h in session.query(StockHolding).filter(StockHolding.is_active == True).all():
                keywords.append(f"{h.ticker} {h.name}")
            for m in session.query(ManualAsset).filter(ManualAsset.is_active == True).all():
                ticker_label = m.ticker.replace("KRW-", "")
                keywords.append(f"{ticker_label} {m.name}")
        return keywords

    @staticmethod
    def _parse_date(entry) -> datetime:
        date_str = entry.get("published") or entry.get("updated")
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
```

- [ ] **Step 2: import 확인**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python3 -c "from services.collectors.google_news import GoogleNewsCollector; print(GoogleNewsCollector.name)"`

Expected: `google_news`

- [ ] **Step 3: 커밋**

```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
git add backend/services/collectors/google_news.py
git commit -m "feat: add Google News RSS collector for portfolio keywords"
```

---

### Task 3: Investing.com 경제캘린더 스크래핑 수집기

**Files:**
- Create: `backend/services/collectors/investing_calendar.py`

- [ ] **Step 1: investing_calendar.py 작성**

`backend/services/collectors/investing_calendar.py`를 다음 내용으로 생성한다:

```python
"""Investing.com 경제캘린더 수집기 — 오늘 주요 경제지표 일정."""

import logging
import re
from datetime import datetime, timezone
from typing import List

import httpx
from bs4 import BeautifulSoup

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

CALENDAR_URL = "https://www.investing.com/economic-calendar/"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@register
class InvestingCalendarCollector(BaseCollector):
    name = "investing_calendar"

    async def collect(self) -> List[RawNewsItem]:
        async with httpx.AsyncClient(
            timeout=20,
            headers={"User-Agent": USER_AGENT},
            follow_redirects=True,
        ) as client:
            resp = await client.get(CALENDAR_URL)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        # 경제캘린더 테이블 행 파싱
        rows = soup.select("tr.js-event-item")
        if not rows:
            # 대체 셀렉터 시도
            rows = soup.select("tr[data-event-datetime]")

        for row in rows:
            try:
                # 중요도 (bull 아이콘 수)
                bulls = row.select("td.sentiment i.grayFullBullishIcon, td.left i.grayFullBullishIcon")
                importance = len(bulls)
                if importance < 3:
                    continue  # 3 bulls 미만 스킵

                # 국가
                country_td = row.select_one("td.flagCur")
                country = country_td.get_text(strip=True) if country_td else ""

                # 시각
                time_td = row.select_one("td.time")
                time_str = time_td.get_text(strip=True) if time_td else ""

                # 지표명
                event_td = row.select_one("td.event a")
                if not event_td:
                    event_td = row.select_one("td.event")
                event_name = event_td.get_text(strip=True) if event_td else ""

                if not event_name:
                    continue

                # 실제/예상/이전 값
                actual = ""
                forecast = ""
                previous = ""
                val_cells = row.select("td.bold")
                if len(val_cells) >= 1:
                    actual = val_cells[0].get_text(strip=True)
                val_cells2 = row.select("td.fore")
                if val_cells2:
                    forecast = val_cells2[0].get_text(strip=True)
                prev_cells = row.select("td.prev")
                if prev_cells:
                    previous = prev_cells[0].get_text(strip=True)

                title = f"[{country}] {event_name} ({time_str})"
                content_parts = []
                if actual:
                    content_parts.append(f"실제: {actual}")
                if forecast:
                    content_parts.append(f"예상: {forecast}")
                if previous:
                    content_parts.append(f"이전: {previous}")
                content = f"{'★' * importance} 중요도. {', '.join(content_parts)}" if content_parts else f"{'★' * importance} 중요도"

                items.append(RawNewsItem(
                    source=self.name,
                    title=title,
                    content=content,
                    url=CALENDAR_URL,
                    published_at=now,
                ))
            except Exception as e:
                logger.debug(f"[investing_calendar] row parse error: {e}")
                continue

        if not items:
            logger.info("[investing_calendar] no high-importance events found (or page structure changed)")

        return items
```

- [ ] **Step 2: import 확인**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python3 -c "from services.collectors.investing_calendar import InvestingCalendarCollector; print(InvestingCalendarCollector.name)"`

Expected: `investing_calendar`

- [ ] **Step 3: 커밋**

```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
git add backend/services/collectors/investing_calendar.py
git commit -m "feat: add Investing.com economic calendar scraping collector"
```

---

### Task 4: scheduler.py에 새 수집기 import 추가

**Files:**
- Modify: `backend/scheduler.py:367-372`

- [ ] **Step 1: generate_news_report()의 수집기 import에 2개 추가**

`backend/scheduler.py`의 `generate_news_report()` 함수 안에서 기존 수집기 import 블록 (367~372행 부근):

```python
    import services.collectors.coindesk
    import services.collectors.cointelegraph
    import services.collectors.yahoo_finance
    import services.collectors.coingecko
    import services.collectors.sec_edgar
    import services.collectors.fear_greed
```

이 블록 끝에 2줄 추가:

```python
    import services.collectors.google_news
    import services.collectors.investing_calendar
```

- [ ] **Step 2: 커밋**

```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
git add backend/scheduler.py
git commit -m "feat(scheduler): register Google News and Investing.com collectors"
```

---

### Task 5: 통합 테스트

**Files:** 없음 (수동 확인)

- [ ] **Step 1: 전체 수집기 실행**

Run:
```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && source venv/bin/activate && python3 -c "
import asyncio
import logging
logging.basicConfig(level=logging.INFO)

import services.collectors.coindesk
import services.collectors.cointelegraph
import services.collectors.yahoo_finance
import services.collectors.coingecko
import services.collectors.sec_edgar
import services.collectors.fear_greed
import services.collectors.google_news
import services.collectors.investing_calendar

from services.collectors import collect_all, COLLECTORS

print(f'Registered collectors: {[c.name for c in COLLECTORS]}')

async def main():
    items = await collect_all()
    by_source = {}
    for item in items:
        by_source.setdefault(item.source, 0)
        by_source[item.source] += 1
    print(f'Total: {len(items)} items')
    for src, cnt in sorted(by_source.items()):
        print(f'  {src}: {cnt}')

asyncio.run(main())
"
```

Expected: 8개 수집기 등록, `google_news`와 `investing_calendar`에서 아이템 수집 확인.

- [ ] **Step 2: 에러가 있으면 수정 후 커밋**
