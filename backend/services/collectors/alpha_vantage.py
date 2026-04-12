"""Alpha Vantage 뉴스 센티먼트 수집기 — 보유 주식 종목별 뉴스."""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List

import httpx
from dotenv import load_dotenv
from sqlalchemy.orm import Session

from database import StockHolding, engine
from services.collectors import BaseCollector, RawNewsItem, register

load_dotenv()
logger = logging.getLogger(__name__)

API_URL = "https://www.alphavantage.co/query"


@register
class AlphaVantageCollector(BaseCollector):
    name = "alpha_vantage"

    async def collect(self) -> List[RawNewsItem]:
        api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")
        if not api_key:
            logger.warning("[alpha_vantage] API key not set, skipping")
            return []

        tickers = self._get_stock_tickers()
        if not tickers:
            logger.info("[alpha_vantage] no stock holdings found, skipping")
            return []

        items: List[RawNewsItem] = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        async with httpx.AsyncClient(timeout=15) as client:
            for ticker in tickers[:3]:  # 무료 25회/일 제한 — 상위 3종목만
                try:
                    resp = await client.get(API_URL, params={
                        "function": "NEWS_SENTIMENT",
                        "tickers": ticker,
                        "limit": 5,
                        "apikey": api_key,
                    })
                    resp.raise_for_status()
                    data = resp.json()

                    for article in data.get("feed", [])[:5]:
                        title = article.get("title", "")
                        summary = article.get("summary", "")
                        url = article.get("url", "")
                        source = article.get("source", "alpha_vantage")
                        time_published = article.get("time_published", "")

                        published_at = None
                        if time_published:
                            try:
                                published_at = datetime.strptime(time_published, "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
                            except Exception:
                                pass

                        sentiment = ""
                        for ts in article.get("ticker_sentiment", []):
                            if ts.get("ticker") == ticker:
                                label = ts.get("ticker_sentiment_label", "")
                                score = ts.get("ticker_sentiment_score", "")
                                sentiment = f" [Sentiment: {label} ({score})]"
                                break

                        if published_at and published_at < cutoff:
                            continue
                        items.append(RawNewsItem(
                            source=self.name,
                            title=f"[{ticker}] {title}{sentiment}",
                            content=summary,
                            url=url,
                            published_at=published_at,
                        ))
                except Exception as e:
                    logger.warning(f"[alpha_vantage] failed for {ticker}: {e}")

        return items

    @staticmethod
    def _get_stock_tickers() -> List[str]:
        with Session(engine) as session:
            holdings = session.query(StockHolding.ticker).filter(
                StockHolding.is_active == True
            ).all()
            return [h.ticker for h in holdings]
