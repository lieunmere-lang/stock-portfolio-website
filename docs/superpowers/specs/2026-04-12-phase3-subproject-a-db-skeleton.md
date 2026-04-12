# Phase 3 서브프로젝트 A: DB 모델 + 수집기/분석기 뼈대 — 설계 문서

## 1. 개요

Phase 3 뉴스 리포트 파이프라인의 기반 구조를 구축한다. DB 모델 정의, 수집기 플러그인 구조, 분석기 함수 뼈대를 만들어 이후 서브프로젝트(B: 수집기 구현, C: Claude 분석)가 바로 코드를 채울 수 있게 한다.

## 2. DB 모델

### 2-1. `NewsReport` (기존 모델 교체)

기존 `news_reports` 테이블은 UI 목업용으로만 생성된 빈 테이블이므로 DROP 후 재생성한다.

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| report_date | String(10), unique | 리포트 대상 날짜 ("2026-04-12") |
| created_at | DateTime | 리포트 생성 시각 |
| summary | Text | Claude 생성 전체 요약 |
| model_used | String(50) | 사용된 Claude 모델명 |
| total_collected | Integer | 수집된 원시 뉴스 총 건수 |
| total_selected | Integer | 선별된 뉴스 건수 |

- `items` relationship → `NewsReportItem` (cascade delete)

### 2-2. `NewsReportItem` (신규)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| report_id | Integer, FK → news_reports.id | |
| category | String(50) | macro, stock, crypto, sentiment, hiring |
| title | Text | Claude 생성 한국어 제목 |
| summary | Text | Claude 생성 한국어 요약 |
| impact_analysis | Text, nullable | 포트폴리오 영향 분석 |
| related_ticker | String(20), nullable | 관련 종목 티커 |
| source | String(50) | 원본 소스명 |
| source_url | Text | 원문 URL |
| importance | Integer | 중요도 (1-5) |

- `report` relationship → `NewsReport`

### 2-3. `RawNews` (신규)

| 컬럼 | 타입 | 설명 |
|------|------|------|
| id | Integer, PK | |
| source | String(50) | 소스명 ("reuters", "coindesk" 등) |
| title | Text | 원본 제목 |
| content | Text | 원본 내용/요약 |
| url | Text | 원문 URL |
| published_at | DateTime, nullable | 원본 발행 시각 |
| collected_at | DateTime | 수집 시각 |

## 3. 수집기 플러그인 구조

### 3-1. 디렉토리 구조

```
backend/services/
├── collectors/
│   ├── __init__.py          # BaseCollector, RawNewsItem, registry, collect_all()
│   └── (소스별 파일은 서브프로젝트 B에서 추가)
└── news_analyzer.py         # analyze_news() 뼈대
```

### 3-2. `RawNewsItem` 데이터클래스

수집기가 반환하는 표준 포맷:

```python
@dataclass
class RawNewsItem:
    source: str                    # 소스명
    title: str                     # 제목
    content: str                   # 내용/요약
    url: str                       # 원문 URL
    published_at: datetime | None  # 발행 시각
```

### 3-3. `BaseCollector` 추상 클래스

```python
class BaseCollector(ABC):
    name: str  # 소스 식별자 ("reuters", "coindesk" 등)

    @abstractmethod
    async def collect(self) -> list[RawNewsItem]:
        """뉴스 수집. 실패 시 빈 리스트 반환."""
        ...
```

### 3-4. 레지스트리

```python
COLLECTORS: list[type[BaseCollector]] = []

def register(cls):
    """데코레이터: 수집기 클래스를 레지스트리에 등록"""
    COLLECTORS.append(cls)
    return cls

async def collect_all() -> list[RawNewsItem]:
    """등록된 모든 수집기 실행. 실패한 소스는 로그 남기고 스킵."""
    results = []
    for collector_cls in COLLECTORS:
        try:
            collector = collector_cls()
            items = await collector.collect()
            results.extend(items)
        except Exception as e:
            logger.warning(f"Collector {collector_cls.name} failed: {e}")
    return results
```

소스별 수집기는 `@register` 데코레이터로 등록하면 `collect_all()`에 자동 포함.

## 4. 분석기 뼈대

### 4-1. `news_analyzer.py`

```python
async def analyze_news(raw_items: list[RawNewsItem], holdings: list[dict]) -> dict:
    """
    Claude API로 뉴스 선별·요약·영향분석 → 리포트 JSON 반환.
    서브프로젝트 C에서 구현.
    """
    raise NotImplementedError
```

단일 함수로 프롬프트 작성, API 호출, 응답 파싱을 모두 처리한다.

## 5. `init_db` 마이그레이션

기존 `news_reports` 테이블이 빈 테이블이므로 DROP 후 재생성한다. `init_db()`에서:

1. 기존 `news_reports` 테이블 DROP
2. `Base.metadata.create_all()`로 모든 테이블 재생성 (news_reports, news_report_items, raw_news 포함)

## 6. 변경 파일

| 파일 | 변경 |
|------|------|
| `backend/database.py` | NewsReport 모델 교체, NewsReportItem·RawNews 모델 추가, init_db 수정 |
| `backend/services/collectors/__init__.py` | 신규 — BaseCollector, RawNewsItem, register, collect_all |
| `backend/services/news_analyzer.py` | 신규 — analyze_news 뼈대 |
