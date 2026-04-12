"""Yahoo Finance 뉴스 수집기 — yfinance 라이브러리 사용."""

import logging
from datetime import datetime, timezone
from typing import List

import yfinance as yf
from sqlalchemy.orm import Session

from database import StockHolding, engine
from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)


@register
class YahooFinanceCollector(BaseCollector):
    name = "yahoo_finance"

    async def collect(self) -> List[RawNewsItem]:
        tickers = self._get_stock_tickers()
        if not tickers:
            logger.info("[yahoo_finance] no stock holdings found, skipping")
            return []

        items: List[RawNewsItem] = []

        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                news = stock.news or []

                for article in news[:5]:
                    content = article.get("content", {}) if isinstance(article.get("content"), dict) else {}
                    title = content.get("title", article.get("title", ""))
                    summary = content.get("summary", article.get("summary", ""))
                    url = content.get("canonicalUrl", {}).get("url", "") if isinstance(content.get("canonicalUrl"), dict) else article.get("link", "")
                    pub_date = content.get("pubDate", article.get("providerPublishTime"))

                    published_at = None
                    if isinstance(pub_date, str):
                        try:
                            published_at = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
                        except Exception:
                            pass
                    elif isinstance(pub_date, (int, float)):
                        published_at = datetime.fromtimestamp(pub_date, tz=timezone.utc)

                    if title:
                        items.append(RawNewsItem(
                            source=self.name,
                            title=f"[{ticker}] {title}",
                            content=summary,
                            url=url,
                            published_at=published_at,
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
