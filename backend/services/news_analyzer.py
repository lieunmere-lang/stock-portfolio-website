"""뉴스 분석기 — Claude API로 뉴스 선별·요약·영향분석.

서브프로젝트 C에서 구현 예정. 현재는 인터페이스만 정의한다.
"""

from __future__ import annotations

from typing import Any, Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from services.collectors import RawNewsItem


async def analyze_news(
    raw_items: list[RawNewsItem],
    holdings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """수집된 원시 뉴스와 보유 종목 정보를 받아 Claude API로 분석한다.

    Args:
        raw_items: collect_all()이 반환한 원시 뉴스 리스트
        holdings: 현재 포트폴리오 보유 종목 리스트
            (각 항목은 {"ticker": "TSLA", "name": "Tesla", ...} 형태)

    Returns:
        리포트 JSON dict:
        {
            "summary": "전체 요약 텍스트",
            "model_used": "claude-haiku-4-5",
            "items": [
                {
                    "category": "macro",
                    "title": "...",
                    "summary": "...",
                    "impact_analysis": "..." or None,
                    "related_ticker": "TSLA" or None,
                    "source": "Reuters",
                    "source_url": "https://...",
                    "importance": 5,
                },
                ...
            ]
        }

    Raises:
        NotImplementedError: 서브프로젝트 C에서 구현 예정.
    """
    raise NotImplementedError("analyze_news는 서브프로젝트 C에서 구현 예정입니다.")
