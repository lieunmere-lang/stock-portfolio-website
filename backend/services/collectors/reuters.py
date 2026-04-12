"""Reuters 뉴스 수집기 — 글로벌 거시경제·지정학 뉴스."""

import logging
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import List

import feedparser
import httpx

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

# Reuters RSS feeds (공개 접근 가능한 피드)
RSS_FEEDS = [
    ("https://www.reutersagency.com/feed/?best-topics=business-finance&post_type=best", "reuters_business"),
    ("https://www.reutersagency.com/feed/?best-topics=tech&post_type=best", "reuters_tech"),
]

USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


@register
class ReutersCollector(BaseCollector):
    name = "reuters"

    async def collect(self) -> List[RawNewsItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        items: List[RawNewsItem] = []

        async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}, follow_redirects=True) as client:
            for feed_url, feed_name in RSS_FEEDS:
                try:
                    resp = await client.get(feed_url)
                    resp.raise_for_status()
                    feed = feedparser.parse(resp.text)

                    for entry in feed.entries[:10]:
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
                    logger.warning(f"[reuters] failed for {feed_name}: {e}")

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
