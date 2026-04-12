"""Bloomberg 뉴스 수집기 — 금융·경제 심층 뉴스 (제목+요약)."""

import logging
from datetime import datetime, timezone
from typing import List

import httpx
from bs4 import BeautifulSoup

from services.collectors import BaseCollector, RawNewsItem, register

logger = logging.getLogger(__name__)

MARKETS_URL = "https://www.bloomberg.com/markets"
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


@register
class BloombergCollector(BaseCollector):
    name = "bloomberg"

    async def collect(self) -> List[RawNewsItem]:
        items: List[RawNewsItem] = []
        now = datetime.now(timezone.utc)

        try:
            async with httpx.AsyncClient(
                timeout=20,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
            ) as client:
                resp = await client.get(MARKETS_URL)
                resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # Bloomberg 기사 링크 추출 (여러 셀렉터 시도)
            articles = soup.select("article a[href*='/news/']")
            if not articles:
                articles = soup.select("a[href*='/news/articles/']")
            if not articles:
                # 제목 태그에서 추출 시도
                articles = soup.select("h3 a, h2 a")

            seen_urls = set()
            for a_tag in articles[:15]:
                href = a_tag.get("href", "")
                if not href or href in seen_urls:
                    continue
                seen_urls.add(href)

                title = a_tag.get_text(strip=True)
                if not title or len(title) < 10:
                    continue

                url = href if href.startswith("http") else f"https://www.bloomberg.com{href}"

                items.append(RawNewsItem(
                    source=self.name,
                    title=title,
                    content="",
                    url=url,
                    published_at=now,
                ))

            if not items:
                logger.info("[bloomberg] no articles found (page structure may have changed)")

        except Exception as e:
            logger.warning(f"[bloomberg] failed: {e}")

        return items
