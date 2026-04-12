"""Investing.com 경제캘린더 수집기 — 오늘 주요 경제지표 일정."""

import logging
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

        rows = soup.select("tr.js-event-item")
        if not rows:
            rows = soup.select("tr[data-event-datetime]")

        for row in rows:
            try:
                bulls = row.select("td.sentiment i.grayFullBullishIcon, td.left i.grayFullBullishIcon")
                importance = len(bulls)
                if importance < 3:
                    continue

                country_td = row.select_one("td.flagCur")
                country = country_td.get_text(strip=True) if country_td else ""

                time_td = row.select_one("td.time")
                time_str = time_td.get_text(strip=True) if time_td else ""

                event_td = row.select_one("td.event a")
                if not event_td:
                    event_td = row.select_one("td.event")
                event_name = event_td.get_text(strip=True) if event_td else ""

                if not event_name:
                    continue

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
