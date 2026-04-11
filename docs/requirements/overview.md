# 프로젝트 개요

## 목표

코인·주식 통합 대시보드 + 분석 + 매일 아침 뉴스 리포트

---

## 현재 구조

```
backend/
  main.py          # FastAPI 서버 + 업비트 API 연동 + HTTP Basic Auth
  requirements.txt
frontend/
  index.html       # Bootstrap + Chart.js 단일 페이지
manage_server.sh   # 백엔드·프론트·ngrok 통합 관리 스크립트
ngrok              # 원격 접속용 터널 바이너리
```

**유지할 것:** FastAPI, APScheduler, ngrok 기반 인프라, Chart.js  
**교체·확장할 것:** 인증 방식, 데이터 저장소, 프론트엔드 구조, 기능 전반

---

## 아키텍처 목표

```
[맥북 로컬]
  FastAPI (port 8000)
    ├── SQLite DB (포트폴리오 이력, 뉴스 캐시)
    ├── APScheduler (데이터 동기화 + 뉴스 수집)
    └── 정적 파일 서빙 (프론트엔드)

[외부 접속]
  Cloudflare Tunnel (무료, 고정 URL)
    └── JWT 로그인 페이지로 인증 → 대시보드 진입

[알림]
  Telegram Bot → 핸드폰으로 매일 9시 뉴스 리포트
```

---

## 목표 프로젝트 구조

```
backend/
  main.py
  database.py        # SQLAlchemy 모델 + DB 초기화
  routers/
    auth.py          # JWT 발급 엔드포인트
    portfolio.py     # 포트폴리오 API
    analytics.py     # 분석 데이터 API
    news.py          # 뉴스 API
  services/
    upbit.py         # 업비트 연동 로직
    kiwoom.py        # 키움증권 연동 (Phase 5)
    news_fetcher.py  # 뉴스 수집 로직
    analyzer.py      # 포트폴리오 분석 로직
    notifier.py      # Telegram 전송 로직
  scheduler.py       # APScheduler 작업 정의
  requirements.txt
frontend/
  index.html         # 로그인 → 대시보드 SPA
  assets/
    main.js
    styles.css
```

---

## 기술 스택

| 구분 | 기술 | 이유 |
|------|------|------|
| 백엔드 | FastAPI + Python 3.11+ | 이미 사용 중, 비동기 지원 |
| DB | SQLite + SQLAlchemy | 개인용 충분, 인프라 불필요 |
| 스케줄러 | APScheduler | 이미 설치됨 |
| 인증 | JWT (python-jose) | 모바일 UX 개선 |
| 원격 접속 | Cloudflare Tunnel | 무료, 고정 URL |
| 알림 | Telegram Bot | 모바일 즉시 수신 |
| 뉴스 | feedparser + NewsAPI | RSS 무료, NewsAPI 무료 티어 |
| 코인 데이터 | CoinGecko API | 무료, 풍부한 데이터 |
| 주식 데이터 | yfinance + 네이버 금융 | 무료 |
| 프론트엔드 | Vanilla JS + Bootstrap 5 | 이미 사용 중, 충분함 |
| 차트 | Chart.js | 이미 사용 중 |

---

## 환경변수 (.env)

```env
# 업비트
UPBIT_ACCESS_KEY=
UPBIT_SECRET_KEY=

# 앱 인증
APP_USERNAME=
APP_PASSWORD=
JWT_SECRET_KEY=

# Telegram
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# NewsAPI (https://newsapi.org 무료 계정)
NEWS_API_KEY=

# Cloudflare Tunnel
CLOUDFLARE_TUNNEL_TOKEN=

# Ngrok (대체 사용 시)
NGROK_AUTHTOKEN=
```

---

## 개발 우선순위

```
[즉시 시작]
Phase 0-1: JWT 인증 (모바일 접속 편의성)
Phase 0-3: Cloudflare Tunnel (핸드폰으로 고정 URL 접속)

[다음]
Phase 1:   포트폴리오 통계 (핵심 가치)
Phase 3:   매일 뉴스 리포트 (Telegram)

[이후]
Phase 2:   종목별 상세 정보 (PER, PSR 등)
Phase 4:   가격 알림, 리밸런싱, 트레이드 저널, 시장 상황판

[나중에]
Phase 5:   키움증권 연동
```

---

## 무료 API 목록

| API | 용도 | 한도 |
|-----|------|------|
| Upbit API | 코인 잔고·시세 | 인증 후 무제한 |
| CoinGecko API | 코인 시세·정보 | 분당 30 요청 |
| Alternative.me | 공포·탐욕 지수 | 무제한 |
| NewsAPI | 키워드 뉴스 검색 | 월 100 요청 (무료) |
| yfinance | 글로벌 주식·ETF 데이터 | 무제한 (비공식) |
| FinanceDataReader | 한국 주식 데이터 | 무제한 |
| 한국은행 ECOS API | 환율·경제 지표 | 무료 (가입 필요) |
| Cloudflare Tunnel | 외부 접속 | 무료 |
| Telegram Bot API | 알림 전송 | 무료 |
