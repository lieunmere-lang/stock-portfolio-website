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
        date_str = entry.get("published") or entry.get("updated")
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
