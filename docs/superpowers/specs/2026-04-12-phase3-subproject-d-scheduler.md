# Phase 3 서브프로젝트 D: 스케줄러 + Mock 교체 — 설계 문서

## 1. 개요

뉴스 리포트 파이프라인을 완성한다. 매일 자동으로 리포트를 생성하는 스케줄러 job 추가, 수동 트리거 API 추가, 기존 Mock 데이터를 실제 DB 조회로 교체.

## 2. 스케줄러 — 뉴스 리포트 생성 job

### 2-1. `generate_news_report()` 함수

`scheduler.py`에 추가. 흐름:

```
1. 수집기 모듈 import (register 실행)
2. collect_all() → RawNewsItem 리스트
3. RawNews 테이블에 원시 뉴스 저장
4. DB에서 보유 종목 조회 (StockHolding + ManualAsset → ticker, name, profit_loss_rate)
5. analyze_news(raw_items, holdings) → 리포트 dict
6. NewsReport + NewsReportItem DB 저장
7. 로그 출력
```

### 2-2. 스케줄 등록

`start_scheduler()`에서 기존 `sync_portfolio` job 아래에 추가:

```python
scheduler.add_job(
    generate_news_report,
    "cron",
    hour=8, minute=50,
    timezone="Asia/Seoul",
    id="news_report",
)
```

매일 08:50 KST에 실행. 서버 시작 시 자동 실행은 하지 않음 (포트폴리오 동기화와 다르게 비용이 발생하므로).

## 3. 수동 트리거 API

### `POST /api/news/generate`

- JWT 인증 필요
- `generate_news_report()`를 호출하여 즉시 리포트 생성
- 생성된 리포트를 응답으로 반환
- 이미 오늘 날짜 리포트가 있으면 덮어쓰기 (upsert)

## 4. Mock 교체 — `news.py` 엔드포인트

### 4-1. `GET /api/news/latest`

DB에서 `NewsReport`를 `created_at` 내림차순으로 1건 조회. items relationship으로 NewsReportItem도 함께 로드.

응답 형식 (기존 Mock과 동일):
```json
{
    "report_date": "2026-04-12",
    "created_at": "2026-04-12T09:00:00",
    "model_used": "claude-haiku-4-5-20251001",
    "total_collected": 56,
    "total_selected": 12,
    "summary": "...",
    "market_indicators": null,
    "items": [...]
}
```

`market_indicators`는 현재 DB에 저장하지 않으므로 `null` 반환. 리포트가 없으면 404.

### 4-2. `GET /api/news/report/{date}`

DB에서 `report_date == date`인 NewsReport 조회. 없으면 404.

### 4-3. `GET /api/news/reports?offset=0&limit=10`

DB에서 NewsReport 목록 조회 (created_at 내림차순, offset/limit). 응답:
```json
{
    "items": [...],
    "total": 45,
    "has_more": true
}
```

각 항목은 `summary_preview` (summary의 앞 60자)를 포함.

## 5. 변경 파일

| 파일 | 변경 |
|------|------|
| `backend/scheduler.py` | `generate_news_report()` 함수 추가, 08:50 cron job 등록 |
| `backend/routers/news.py` | Mock 데이터 전체 제거, DB 조회 3개 엔드포인트 + POST /generate 추가 |
