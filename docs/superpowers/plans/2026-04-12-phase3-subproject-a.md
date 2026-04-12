# Phase 3 서브프로젝트 A: DB 모델 + 수집기/분석기 뼈대 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 뉴스 리포트 파이프라인의 기반 구조(DB 모델, 수집기 플러그인 인터페이스, 분석기 뼈대)를 구축한다.

**Architecture:** `database.py`에 3개 모델 정의(NewsReport 교체, NewsReportItem·RawNews 추가). `services/collectors/__init__.py`에 BaseCollector 추상 클래스와 레지스트리. `services/news_analyzer.py`에 analyze_news 뼈대.

**Tech Stack:** Python 3.9, SQLAlchemy, FastAPI

**Spec:** `docs/superpowers/specs/2026-04-12-phase3-subproject-a-db-skeleton.md`

**Note:** Python 3.9이므로 `datetime | None` 대신 `Optional[datetime]`을 사용한다.

---

### Task 1: DB 모델 — NewsReport 교체 + NewsReportItem·RawNews 추가

**Files:**
- Modify: `backend/database.py:6-9` (import 추가)
- Modify: `backend/database.py:67-77` (NewsReport 모델 교체)
- Modify: `backend/database.py:120-136` (init_db 수정)

- [ ] **Step 1: import에 `Date` 추가**

`backend/database.py`의 import 문 (6~9행)을 수정한다. 기존:

```python
from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship
```

변경:

```python
from sqlalchemy import (
    Boolean, Column, Date, DateTime, Float, ForeignKey,
    Integer, String, Text, create_engine, event, text,
)
from sqlalchemy.orm import DeclarativeBase, Session, relationship
```

(`Date` 추가)

- [ ] **Step 2: NewsReport 모델 교체**

`backend/database.py`의 기존 NewsReport 클래스 (67~77행)를 다음으로 교체한다:

```python
class NewsReport(Base):
    __tablename__ = "news_reports"

    id = Column(Integer, primary_key=True)
    report_date = Column(String(10), nullable=False, unique=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    summary = Column(Text)
    model_used = Column(String(50))
    total_collected = Column(Integer)
    total_selected = Column(Integer)

    items = relationship("NewsReportItem", back_populates="report", cascade="all, delete-orphan")
```

- [ ] **Step 3: NewsReportItem 모델 추가**

NewsReport 클래스 직후, PriceAlert 클래스 직전에 다음을 추가한다:

```python
class NewsReportItem(Base):
    __tablename__ = "news_report_items"

    id = Column(Integer, primary_key=True)
    report_id = Column(Integer, ForeignKey("news_reports.id"), nullable=False)
    category = Column(String(50))
    title = Column(Text)
    summary = Column(Text)
    impact_analysis = Column(Text)
    related_ticker = Column(String(20))
    source = Column(String(50))
    source_url = Column(Text)
    importance = Column(Integer)

    report = relationship("NewsReport", back_populates="items")
```

- [ ] **Step 4: RawNews 모델 추가**

NewsReportItem 클래스 직후, PriceAlert 클래스 직전에 다음을 추가한다:

```python
class RawNews(Base):
    __tablename__ = "raw_news"

    id = Column(Integer, primary_key=True)
    source = Column(String(50))
    title = Column(Text)
    content = Column(Text)
    url = Column(Text)
    published_at = Column(DateTime)
    collected_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 5: init_db에 news_reports 테이블 DROP 추가**

`backend/database.py`의 `init_db()` 함수를 수정한다. `Base.metadata.create_all(bind=engine)` 호출 직전에 기존 news_reports 테이블을 DROP한다:

기존:
```python
def init_db():
    Base.metadata.create_all(bind=engine)
    # 기존 DB에 새 컬럼 추가 (이미 존재하면 무시)
    migration_stmts = [
```

변경:
```python
def init_db():
    # 기존 news_reports 테이블 DROP (빈 테이블, 스키마 변경을 위해)
    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS news_reports"))
        conn.commit()
    Base.metadata.create_all(bind=engine)
    # 기존 DB에 새 컬럼 추가 (이미 존재하면 무시)
    migration_stmts = [
```

- [ ] **Step 6: 서버 재시작 후 테이블 생성 확인**

Run: `cd backend && python3 -c "from database import init_db; init_db(); from database import engine; from sqlalchemy import inspect; i = inspect(engine); print(sorted(i.get_table_names()))"`

Expected: 리스트에 `news_report_items`, `news_reports`, `raw_news`가 포함되어야 한다.

- [ ] **Step 7: 커밋**

```bash
git add backend/database.py
git commit -m "feat(db): replace NewsReport model, add NewsReportItem and RawNews models"
```

---

### Task 2: 수집기 플러그인 구조 — BaseCollector + registry

**Files:**
- Create: `backend/services/collectors/__init__.py`

- [ ] **Step 1: collectors 디렉토리 생성 및 `__init__.py` 작성**

`backend/services/collectors/__init__.py`를 다음 내용으로 생성한다:

```python
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
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.collectors import BaseCollector, RawNewsItem, register, collect_all; print('OK')"`

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/collectors/__init__.py
git commit -m "feat: add news collector plugin structure (BaseCollector + registry)"
```

---

### Task 3: 분석기 뼈대 — news_analyzer.py

**Files:**
- Create: `backend/services/news_analyzer.py`

- [ ] **Step 1: news_analyzer.py 작성**

`backend/services/news_analyzer.py`를 다음 내용으로 생성한다:

```python
"""뉴스 분석기 — Claude API로 뉴스 선별·요약·영향분석.

서브프로젝트 C에서 구현 예정. 현재는 인터페이스만 정의한다.
"""

from typing import Any, Dict, List

from services.collectors import RawNewsItem


async def analyze_news(
    raw_items: List[RawNewsItem],
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
```

- [ ] **Step 2: import 확인**

Run: `cd backend && python3 -c "from services.news_analyzer import analyze_news; print('OK')"`

Expected: `OK`

- [ ] **Step 3: 커밋**

```bash
git add backend/services/news_analyzer.py
git commit -m "feat: add news_analyzer skeleton with analyze_news interface"
```

---

### Task 4: Mock API를 새 DB 모델과 호환되게 유지

**Files:**
- Modify: `backend/routers/news.py:1-5` (import 추가)

현재 `news.py`의 Mock 데이터는 프론트엔드가 사용 중이다. 새 DB 모델을 추가했지만, 실제 DB 조회로 교체하는 건 서브프로젝트 D에서 한다. 이 Task에서는 Mock 응답의 `market_indicators` 필드가 프론트엔드와 호환되는지만 확인한다.

- [ ] **Step 1: 서버 재시작 후 기존 기능 확인**

서버를 재시작하고 기존 뉴스 페이지(`/news.html`)와 대시보드 뉴스 미리보기가 정상 동작하는지 확인한다.

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website && ./manage_server.sh stop && ./manage_server.sh start`

브라우저에서 `http://localhost:8000`과 `http://localhost:8000/news.html` 접속 확인.

- [ ] **Step 2: 최종 확인 커밋 (변경 있을 경우에만)**

변경 사항이 있으면 커밋한다.
