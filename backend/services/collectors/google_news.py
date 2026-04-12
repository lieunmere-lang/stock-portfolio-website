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
