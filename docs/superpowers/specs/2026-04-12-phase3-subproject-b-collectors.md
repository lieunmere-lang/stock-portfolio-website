# Phase 3 서브프로젝트 B: 뉴스 수집기 1차 (무료 6개) — 설계 문서

## 1. 개요

API 키 없이 바로 사용할 수 있는 무료 소스 6개의 수집기를 구현한다. 서브프로젝트 A에서 만든 BaseCollector 플러그인 구조에 각 수집기를 등록한다.

## 2. 수집기 목록

### 2-1. RSS 수집기 (3개)

| 소스 | 파일 | RSS URL | 역할 |
|------|------|---------|------|
| Yahoo Finance | `yahoo_finance.py` | `https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}` | 보유 주식 종목별 뉴스 |
| CoinDesk | `coindesk.py` | `https://www.coindesk.com/arc/outboundfeeds/rss/` | 크립토 전반 뉴스 |
| Cointelegraph | `cointelegraph.py` | `https://cointelegraph.com/rss` | 크립토/블록체인 뉴스 |

### 2-2. API 수집기 (3개)

| 소스 | 파일 | API | 역할 |
|------|------|-----|------|
| CoinGecko | `coingecko.py` | `https://api.coingecko.com/api/v3/search/trending` | 트렌딩 코인 데이터 |
| SEC EDGAR | `sec_edgar.py` | `https://efts.sec.gov/LATEST/search-index?q={ticker}` | 보유 주식 공시/내부자거래 |
| Fear & Greed | `fear_greed.py` | CNN + Alternative.me | 주식/크립토 시장 심리 지표 |

## 3. 공통 사항

### 3-1. HTTP 클라이언트

`httpx.AsyncClient`를 사용한다. 각 수집기가 자체 client를 생성한다 (간단한 요청이므로 공유 불필요).

### 3-2. 시간 필터

RSS 수집기는 최근 24시간 이내 발행된 뉴스만 수집한다. `published_at`이 없거나 파싱 실패 시 포함한다 (누락보다 중복이 나음).

### 3-3. 에러 처리

각 수집기는 독립적으로 실행된다. 실패 시 빈 리스트 반환 또는 예외 발생 → `collect_all()`이 로그 남기고 스킵.

## 4. 수집기별 상세

### 4-1. Yahoo Finance

- DB에서 `StockHolding` 테이블의 활성 종목 티커 목록 조회
- 각 티커별로 `https://feeds.finance.yahoo.com/rss/2.0/headline?s={ticker}` 호출
- `feedparser`로 파싱, 최근 24시간 뉴스만 필터
- `RawNewsItem` 변환: source="yahoo_finance", title=entry.title, content=entry.summary, url=entry.link

### 4-2. CoinDesk

- `https://www.coindesk.com/arc/outboundfeeds/rss/` 호출
- `feedparser`로 파싱, 최근 24시간 뉴스만 필터
- `RawNewsItem` 변환: source="coindesk"

### 4-3. Cointelegraph

- `https://cointelegraph.com/rss` 호출
- `feedparser`로 파싱, 최근 24시간 뉴스만 필터
- `RawNewsItem` 변환: source="cointelegraph"

### 4-4. CoinGecko

- `https://api.coingecko.com/api/v3/search/trending` 호출 (키 불필요, 30회/분 제한)
- 트렌딩 코인 목록에서 상위 7개의 이름, 심볼, 시가총액 순위, 24h 가격 변동을 수집
- `RawNewsItem` 변환: source="coingecko", title="[Trending] {coin} — 24h {change}%", content=상세 정보

### 4-5. SEC EDGAR

- DB에서 `StockHolding` 테이블의 활성 종목 티커 목록 조회
- 각 티커별로 EDGAR Full-Text Search API 호출
  - `https://efts.sec.gov/LATEST/search-index?q="{ticker}"&dateRange=custom&startdt={yesterday}&enddt={today}&forms=4,8-K,10-Q,10-K`
- User-Agent 헤더 필수: `"StockPortfolio/1.0 (contact@example.com)"`
- `RawNewsItem` 변환: source="sec_edgar", title=filing type + company name, url=filing URL

### 4-6. Fear & Greed Index

- CNN Fear & Greed (주식): `https://production.dataviz.cnn.io/index/fearandgreed/graphdata` 호출
- Alternative.me (크립토): `https://api.alternative.me/fng/?limit=1` 호출
- 각각 현재 지수값과 라벨을 수집
- `RawNewsItem` 변환: source="fear_greed", title="Fear & Greed Index: {value} ({label})", content=상세 설명

## 5. 의존성

`requirements.txt`에 추가:
- `feedparser` — RSS 피드 파싱
- `httpx` — async HTTP 클라이언트

## 6. 파일 구조

```
backend/services/collectors/
├── __init__.py          # (이미 존재 — BaseCollector, register, collect_all)
├── yahoo_finance.py     # @register — RSS, 보유 주식 뉴스
├── coindesk.py          # @register — RSS, 크립토 뉴스
├── cointelegraph.py     # @register — RSS, 크립토 뉴스
├── coingecko.py         # @register — API, 트렌딩 코인
├── sec_edgar.py         # @register — API, 공시/내부자거래
└── fear_greed.py        # @register — API, 시장 심리 지표
```

## 7. 변경 파일 요약

| 파일 | 변경 |
|------|------|
| `backend/requirements.txt` | feedparser, httpx 추가 |
| `backend/services/collectors/yahoo_finance.py` | 신규 |
| `backend/services/collectors/coindesk.py` | 신규 |
| `backend/services/collectors/cointelegraph.py` | 신규 |
| `backend/services/collectors/coingecko.py` | 신규 |
| `backend/services/collectors/sec_edgar.py` | 신규 |
| `backend/services/collectors/fear_greed.py` | 신규 |
