"""뉴스 수집기 플러그인 구조.

각 소스별 수집기는 BaseCollector를 상속하고 @register 데코레이터로 등록한다.
collect_all()을 호출하면 등록된 모든 수집기가 실행된다.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class RawNewsItem:
    """수집기가 반환하는 원시 뉴스 표준 포맷."""
    source: str
    title: str
    content: str
    url: str
    published_at: Optional[datetime]


class BaseCollector(ABC):
    """뉴스 수집기 추상 클래스. 각 소스별로 상속하여 구현한다."""
    name: str = "unknown"

    @abstractmethod
    async def collect(self) -> List[RawNewsItem]:
        """뉴스를 수집하여 RawNewsItem 리스트로 반환한다.
        실패 시 빈 리스트를 반환하거나 예외를 발생시킨다 (collect_all이 처리).
        """
        ...


COLLECTORS: List[type] = []


def register(cls):
    """수집기 클래스를 레지스트리에 등록하는 데코레이터."""
    COLLECTORS.append(cls)
    return cls


async def collect_all() -> List[RawNewsItem]:
    """등록된 모든 수집기를 실행한다. 실패한 소스는 로그 남기고 스킵."""
    results: List[RawNewsItem] = []
    for collector_cls in COLLECTORS:
        try:
            collector = collector_cls()
            items = await collector.collect()
            results.extend(items)
            logger.info(f"[{collector.name}] collected {len(items)} items")
        except Exception as e:
            logger.warning(f"[{collector_cls.name}] failed: {e}")
    return results
