"""뉴스 분석기 — Claude API로 뉴스 선별·요약·영향분석."""

import json
import logging
import os
from typing import Any, Dict, List

import anthropic
from dotenv import load_dotenv

from services.collectors import RawNewsItem

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-haiku-4-5-20251001"
DEFAULT_MAX_ITEMS = 15

SYSTEM_PROMPT = """너는 개인 투자자의 포트폴리오 뉴스 분석가다.

## 역할
- 제공된 원시 뉴스에서 투자에 중요한 뉴스 10~15건을 선별한다.
- 각 뉴스를 한국어로 요약하고 카테고리를 분류한다.
- 보유 종목과 관련된 뉴스에는 포트폴리오 영향 분석을 추가한다.
- 전체 시장 상황을 2~3문장으로 요약한다.

## 카테고리
- macro: 거시경제, 금리, 환율, 지정학
- stock: 주식 종목 관련
- crypto: 암호화폐 관련
- sentiment: 시장 심리, 소셜 트렌드
- hiring: 채용, 기업 트렌드

## 중요도 (1-5)
- 5: 포트폴리오에 직접 영향, 긴급
- 4: 시장 전반에 중요
- 3: 참고할 만함
- 2: 배경 정보
- 1: 부수적

## 응답 형식
반드시 아래 JSON 형식으로만 응답한다. 다른 텍스트를 포함하지 않는다.

{
    "summary": "전체 시장 상황 요약 (한국어, 2~3문장)",
    "items": [
        {
            "category": "macro|stock|crypto|sentiment|hiring",
            "title": "한국어 제목",
            "summary": "한국어 요약 (2~3문장)",
            "impact_analysis": "포트폴리오 영향 분석 (보유 종목 관련 시)" 또는 null,
            "related_ticker": "관련 보유 종목 티커" 또는 null,
            "source": "원본 소스명",
            "source_url": "원문 URL",
            "importance": 1~5
        }
    ]
}"""


def _build_user_message(
    raw_items: List[RawNewsItem],
    holdings: List[Dict[str, Any]],
    max_items: int,
) -> str:
    """프롬프트의 user message를 구성한다."""
    holdings_text = json.dumps(
        [{"ticker": h["ticker"], "name": h["name"],
          "profit_loss_rate": round(h.get("profit_loss_rate", 0), 4)}
         for h in holdings],
        ensure_ascii=False,
    )

    news_lines = []
    for i, item in enumerate(raw_items, 1):
        content_preview = (item.content or "")[:200]
        news_lines.append(
            f"{i}. [{item.source}] {item.title}\n"
            f"   내용: {content_preview}\n"
            f"   URL: {item.url}"
        )
    news_text = "\n\n".join(news_lines)

    return (
        f"## 보유 종목\n{holdings_text}\n\n"
        f"## 수집된 뉴스 ({len(raw_items)}건)\n{news_text}\n\n"
        f"위 뉴스에서 중요한 뉴스를 최대 {max_items}건 선별하여 분석하라."
    )


def _parse_response(text: str) -> Dict[str, Any]:
    """Claude 응답에서 JSON을 파싱한다."""
    cleaned = text.strip()
    # 코드블록으로 감싸져 있을 경우 제거
    if cleaned.startswith("```"):
        first_newline = cleaned.index("\n")
        last_fence = cleaned.rfind("```")
        cleaned = cleaned[first_newline + 1:last_fence].strip()

    return json.loads(cleaned)


def _empty_report(model: str) -> Dict[str, Any]:
    """빈 리포트를 반환한다."""
    return {
        "summary": "",
        "model_used": model,
        "items": [],
    }


async def analyze_news(
    raw_items: List[RawNewsItem],
    holdings: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """수집된 원시 뉴스와 보유 종목 정보를 받아 Claude API로 분석한다.

    Args:
        raw_items: collect_all()이 반환한 원시 뉴스 리스트
        holdings: 보유 종목 리스트
            [{"ticker": "TSLA", "name": "Tesla", "profit_loss_rate": 0.15}, ...]

    Returns:
        리포트 dict (summary, model_used, items)
    """
    model = os.getenv("NEWS_CLAUDE_MODEL", DEFAULT_MODEL)
    max_items = int(os.getenv("NEWS_MAX_ITEMS", str(DEFAULT_MAX_ITEMS)))

    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.warning("ANTHROPIC_API_KEY가 설정되지 않았습니다. 빈 리포트를 반환합니다.")
        return _empty_report(model)

    if not raw_items:
        logger.info("수집된 뉴스가 없습니다. 빈 리포트를 반환합니다.")
        return _empty_report(model)

    user_message = _build_user_message(raw_items, holdings, max_items)

    client = anthropic.Anthropic(api_key=api_key)

    response = client.messages.create(
        model=model,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    response_text = response.content[0].text

    try:
        report_data = _parse_response(response_text)
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"Claude 응답 JSON 파싱 실패: {e}")
        logger.debug(f"응답 원문: {response_text[:500]}")
        return _empty_report(model)

    report_data["model_used"] = model
    return report_data
