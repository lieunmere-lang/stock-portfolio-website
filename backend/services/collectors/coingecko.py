"""CoinGecko API 수집기 — 트렌딩 코인 데이터."""

import logging
from datetime import datetime, timezone
from typing import List

import httpx

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

TRENDING_URL = "https://api.coingecko.com/api/v3/search/trending"


@register
class CoinGeckoCollector(BaseCollector):
    name = "coingecko"

    async def collect(self) -> List[RawNewsItem]:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(TRENDING_URL)
            resp.raise_for_status()

        data = resp.json()
        coins = data.get("coins", [])[:7]
        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        for coin_wrap in coins:
            coin = coin_wrap.get("item", {})
            name = coin.get("name", "Unknown")
            symbol = coin.get("symbol", "")
            market_cap_rank = coin.get("market_cap_rank", "N/A")
            price_change_24h = coin.get("data", {}).get("price_change_percentage_24h", {})
            usd_change = price_change_24h.get("usd", 0) if isinstance(price_change_24h, dict) else 0

            sign = "+" if usd_change >= 0 else ""
            title = f"[Trending] {name} ({symbol}) — 24h {sign}{usd_change:.1f}%"
            content = f"Market cap rank: #{market_cap_rank}. 24h price change: {sign}{usd_change:.1f}%"

            items.append(RawNewsItem(
                source=self.name,
                title=title,
                content=content,
                url=f"https://www.coingecko.com/en/coins/{coin.get('id', '')}",
                published_at=now,
            ))

        return items
