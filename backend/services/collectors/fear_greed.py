"""Fear & Greed Index 수집기 — 주식(CNN) + 크립토(Alternative.me) 시장 심리."""

import logging
from datetime import datetime, timezone
from typing import List

import httpx

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

CNN_URL = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
CRYPTO_URL = "https://api.alternative.me/fng/?limit=1"


@register
class FearGreedCollector(BaseCollector):
    name = "fear_greed"

    async def collect(self) -> List[RawNewsItem]:
        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        # CNN Fear & Greed (주식)
        try:
            headers = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}
            async with httpx.AsyncClient(timeout=15, headers=headers) as client:
                resp = await client.get(CNN_URL)
                resp.raise_for_status()
                data = resp.json()

            score = data.get("fear_and_greed", {}).get("score", None)
            rating = data.get("fear_and_greed", {}).get("rating", "")
            if score is not None:
                items.append(RawNewsItem(
                    source=self.name,
                    title=f"CNN Fear & Greed Index: {score:.0f} ({rating})",
                    content=f"Stock market sentiment: {rating}. Score: {score:.0f}/100.",
                    url="https://edition.cnn.com/markets/fear-and-greed",
                    published_at=now,
                ))
        except Exception as e:
            logger.warning(f"[fear_greed] CNN fetch failed: {e}")

        # Crypto Fear & Greed (Alternative.me)
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(CRYPTO_URL)
                resp.raise_for_status()
                data = resp.json()

            fng_data = data.get("data", [{}])[0]
            value = fng_data.get("value", "")
            classification = fng_data.get("value_classification", "")
            if value:
                items.append(RawNewsItem(
                    source=self.name,
                    title=f"Crypto Fear & Greed Index: {value} ({classification})",
                    content=f"Crypto market sentiment: {classification}. Score: {value}/100.",
                    url="https://alternative.me/crypto/fear-and-greed-index/",
                    published_at=now,
                ))
        except Exception as e:
            logger.warning(f"[fear_greed] Crypto fetch failed: {e}")

        return items
