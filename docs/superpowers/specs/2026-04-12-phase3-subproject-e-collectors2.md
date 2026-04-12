# Phase 3 서브프로젝트 E: 수집기 2차 (Google News + Investing.com) — 설계 문서

## 1. 개요

스크래핑/RSS 기반 수집기 2개를 추가한다. 기존 플러그인 구조(`@register`)에 등록하면 `collect_all()`에 자동 포함되어 Claude 분석에 넘어간다.

## 2. 수집기

### 2-1. Google News (`google_news.py`)

- 방식: Google News RSS
- URL: `https://news.google.com/rss/search?q={keyword}&hl=ko&gl=KR&ceid=KR:ko`
- DB에서 보유 종목 조회 (StockHolding + ManualAsset) → 티커/이름으로 키워드 생성
- 종목별 RSS 호출, `feedparser`로 파싱
- 최근 24시간 뉴스만 필터
- 다른 수집기에서 놓친 뉴스를 잡는 안전망 역할

### 2-2. Investing.com 경제캘린더 (`investing_calendar.py`)

- 방식: HTML 스크래핑
- URL: `https://www.investing.com/economic-calendar/`
- 오늘 발표 예정인 주요 경제지표 수집
- 중요도 3 bulls(★★★) 이상만 필터
- `httpx` + `BeautifulSoup`으로 파싱
- User-Agent 헤더 필수 (봇 차단 우회)
- 수집 항목: 시각, 국가, 지표명, 실제값/예상값/이전값

## 3. 의존성

`requirements.txt`에 추가:
- `beautifulsoup4` — HTML 파싱

## 4. 변경 파일

| 파일 | 변경 |
|------|------|
| `backend/requirements.txt` | `beautifulsoup4` 추가 |
| `backend/services/collectors/google_news.py` | 신규 — @register |
| `backend/services/collectors/investing_calendar.py` | 신규 — @register |
| `backend/scheduler.py` | generate_news_report()에 새 수집기 import 추가 |
