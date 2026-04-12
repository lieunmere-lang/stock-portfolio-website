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
        with Session(engine) as session:
            holdings = session.query(StockHolding.ticker).filter(
                StockHolding.is_active == True
            ).all()
            return [h.ticker for h in holdings]

    @staticmethod
    def _parse_date(entry) -> datetime:
        date_str = entry.get("published") or entry.get("updated")
        if not date_str:
            return None
        try:
            return parsedate_to_datetime(date_str)
        except Exception:
            return None
