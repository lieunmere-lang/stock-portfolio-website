"""FRED API 수집기 — 주요 경제지표 최신 데이터."""

import logging
import os
from datetime import datetime, timezone
from typing import List

import httpx
from dotenv import load_dotenv

from services.collectors import BaseCollector, RawNewsItem, register

load_dotenv()
logger = logging.getLogger(__name__)

API_URL = "https://api.stlouisfed.org/fred/series/observations"

# 주요 경제지표 시리즈
SERIES = {
    "FEDFUNDS": "연방기금금리 (Fed Funds Rate)",
    "CPIAUCSL": "소비자물가지수 (CPI)",
    "UNRATE": "실업률 (Unemployment Rate)",
    "DGS10": "미국 10년물 국채 수익률",
    "DEXKOUS": "원/달러 환율 (KRW/USD)",
}


@register
class FredCollector(BaseCollector):
    name = "fred"

    async def collect(self) -> List[RawNewsItem]:
        api_key = os.getenv("FRED_API_KEY", "")
        if not api_key:
            logger.warning("[fred] API key not set, skipping")
            return []

        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        async with httpx.AsyncClient(timeout=15) as client:
            for series_id, label in SERIES.items():
                try:
                    resp = await client.get(API_URL, params={
                        "series_id": series_id,
                        "api_key": api_key,
                        "file_type": "json",
                        "sort_order": "desc",
                        "limit": 1,
                    })
                    resp.raise_for_status()
                    data = resp.json()

                    observations = data.get("observations", [])
                    if not observations:
                        continue

                    obs = observations[0]
                    value = obs.get("value", "N/A")
                    date = obs.get("date", "")

                    items.append(RawNewsItem(
                        source=self.name,
                        title=f"[FRED] {label}: {value} ({date})",
                        content=f"{label} ({series_id}) 최신값: {value}. 기준일: {date}.",
                        url=f"https://fred.stlouisfed.org/series/{series_id}",
                        published_at=now,
                    ))
                except Exception as e:
                    logger.warning(f"[fred] failed for {series_id}: {e}")

        return items
