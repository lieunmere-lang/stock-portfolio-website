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
        with Session(engine) as session:
            holdings = session.query(StockHolding.ticker).filter(
                StockHolding.is_active == True
            ).all()
            return [h.ticker for h in holdings]
