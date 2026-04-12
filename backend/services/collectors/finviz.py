"""Finviz 수집기 — 섹터별 퍼포먼스 + 보유 종목 뉴스."""

import logging
from datetime import datetime, timezone
from typing import List

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from database import StockHolding, engine
from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

NEWS_URL_TEMPLATE = "https://finviz.com/quote.ashx?t={ticker}"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@register
class FinvizCollector(BaseCollector):
    name = "finviz"

    async def collect(self) -> List[RawNewsItem]:
        tickers = self._get_stock_tickers()
        if not tickers:
            logger.info("[finviz] no stock holdings found, skipping")
            return []

        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(
            timeout=15,
            headers={"User-Agent": USER_AGENT},
        ) as client:
            for ticker in tickers[:5]:  # 상위 5종목
                try:
                    url = NEWS_URL_TEMPLATE.format(ticker=ticker)
                    resp = await client.get(url)
                    resp.raise_for_status()

                    soup = BeautifulSoup(resp.text, "html.parser")

                    # 뉴스 테이블 추출
                    news_table = soup.select_one("table.fullview-news-outer")
                    if not news_table:
                        news_table = soup.select_one("#news-table")

                    if not news_table:
                        logger.debug(f"[finviz] no news table found for {ticker}")
                        continue

                    rows = news_table.select("tr")
                    for row in rows[:5]:
                        a_tag = row.select_one("a")
                        if not a_tag:
                            continue

                        title = a_tag.get_text(strip=True)
                        news_url = a_tag.get("href", "")
                        source_span = row.select_one("span")
                        source_name = source_span.get_text(strip=True) if source_span else "finviz"

                        if title:
                            items.append(RawNewsItem(
                                source=self.name,
                                title=f"[{ticker}] {title}",
                                content=f"Source: {source_name}",
                                url=news_url,
                                published_at=now,
                            ))
                except Exception as e:
                    logger.warning(f"[finviz] failed for {ticker}: {e}")

        return items

    @staticmethod
    def _get_stock_tickers() -> List[str]:
        with Session(engine) as session:
            holdings = session.query(StockHolding.ticker).filter(
                StockHolding.is_active == True
            ).all()
            return [h.ticker for h in holdings]
