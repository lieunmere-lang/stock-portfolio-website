# 개인 맞춤형 투자 포트폴리오 웹사이트 — 개발 계획서

> 작성일: 2026-04-11  
> 현재 상태: FastAPI + 업비트 연동 기본 구조 완성  
> 목표: 코인·주식 통합 대시보드 + 분석 + 매일 아침 뉴스 리포트

---

## 1. 현재 구조 요약

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

## 2. 아키텍처 목표

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

## 3. 개발 로드맵

### Phase 0: 기반 정비 (1~2일)

#### 0-1. 인증 방식 개선 — HTTP Basic → JWT 로그인 페이지
- 현재 Basic Auth는 브라우저 팝업으로 모바일 UX가 나쁨
- `/login` HTML 페이지에서 아이디·비밀번호 입력 → JWT 토큰 발급
- 프론트엔드는 `localStorage`에 JWT 저장, 모든 API 요청에 Bearer 헤더 첨부
- 토큰 만료 시 자동으로 로그인 페이지로 리다이렉트

#### 0-2. SQLite 데이터베이스 도입
- `SQLAlchemy` + `aiosqlite` 사용
- 테이블 구조:

```
portfolio_snapshots  # 시간별 포트폴리오 스냅샷 (이력 차트용)
  id, timestamp, total_value, total_profit_loss, total_profit_loss_rate

assets               # 개별 자산 스냅샷
  id, snapshot_id, name, ticker, quantity, avg_price, current_price,
  total_value, profit_loss, profit_loss_rate, asset_type

news_reports         # 수집된 뉴스 캐시
  id, created_at, category, title, summary, source, url

price_alerts         # 가격 알림 설정 (Phase 4)
  id, ticker, condition, threshold, is_active
```

#### 0-3. Cloudflare Tunnel 설정 (ngrok 대체)
- 무료, 고정 URL, 인증 없이도 HTTPS 지원
- `cloudflared tunnel` 바이너리 설치 후 `manage_server.sh`에 통합
- ngrok은 URL이 매번 바뀌어 핸드폰 북마크 불가 → Cloudflare로 해결

#### 0-4. 프로젝트 구조 정리

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

### Phase 1: 포트폴리오 통계 및 데이터 분석 (3~5일)

#### 1-1. 대시보드 요약 카드 (상단)

| 카드 | 내용 |
|------|------|
| 총 평가금액 | 전체 자산 합계 (KRW) |
| 총 손익 | 금액 + 수익률 |
| 오늘의 손익 | 당일 변동 |
| 투자 원금 | 총 매수 금액 |
| 포트폴리오 베타 | 시장 대비 변동성 지수 |

#### 1-2. 수익률 분석

- **기간별 수익률**: 1일, 1주, 1개월, 3개월, 6개월, 1년 (DB 스냅샷 기반)
- **누적 수익률 차트**: 시간축 라인 차트 (Chart.js)
- **최대 낙폭(MDD)**: 고점 대비 최대 하락률
- **변동성**: 일별 수익률의 표준편차 (30일 기준)
- **샤프 지수**: (수익률 - 무위험이자율) / 변동성 → 위험 대비 수익 효율

#### 1-3. 자산 배분 분석

- **자산 유형별 비중**: 코인 vs 주식 파이 차트
- **종목별 비중**: 도넛 차트 (이미 구현됨 → 개선)
- **상위 5 종목**: 수익 기여도 순
- **헥사맵 (Treemap)**: 보유 비중을 시각적으로 표시

#### 1-4. 리스크 지표

- **집중도 위험**: HHI(허핀달-허슈만 지수) — 단일 종목 과집중 경고
- **상관관계 매트릭스**: 보유 코인 간 가격 움직임 상관도 히트맵
- **포트폴리오 분산도**: 자산 수 / 업종 다양성

---

### Phase 2: 종목별 상세 정보 (3~4일)

각 코인·주식 클릭 시 상세 모달 또는 사이드 패널 표시

#### 2-1. 코인 (업비트 기준) — CoinGecko API 활용 (무료)

| 항목 | 설명 |
|------|------|
| 시가총액 | Market Cap (KRW/USD) |
| 거래량 (24h) | 24시간 거래량 |
| 유통 공급량 | Circulating Supply |
| 전체 공급량 | Total Supply |
| 52주 고/저 | 연간 최고·최저가 |
| 도미넌스 | 해당 코인의 시장 점유율 |
| 공식 사이트 / 백서 링크 | 기본 정보 |

#### 2-2. 주식 (키움증권 추가 시) — 네이버 금융 + Yahoo Finance

| 항목 | 설명 |
|------|------|
| PER | 주가수익비율 (Price/Earnings) |
| PBR | 주가순자산비율 (Price/Book) |
| PSR | 주가매출비율 (Price/Sales) |
| EV/EBITDA | 기업가치 대비 영업이익 |
| ROE / ROA | 자기자본·총자산 수익률 |
| 배당수익률 | 연간 배당 / 현재가 |
| 실적 발표일 | 다음 어닝 날짜 (Earnings Date) |
| 시장 컨센서스 | 애널리스트 목표가 + 매수/중립/매도 비율 |
| 52주 고/저 | 연간 최고·최저가 |
| 외인·기관 순매수 | 최근 수급 동향 |

**데이터 소스:**
- 코인 기본 정보: [CoinGecko API](https://www.coingecko.com/api) (무료, 분당 30 요청)
- 주식 지표: `yfinance` Python 라이브러리 (무료)
- 한국 주식 컨센서스: 네이버 금융 비공식 API (스크래핑)
- 실적 발표일: Yahoo Finance Earnings Calendar

---

### Phase 3: 매일 아침 9시 뉴스 리포트 (4~5일)

#### 3-1. 수집 카테고리

| 카테고리 | 내용 | 소스 |
|----------|------|------|
| 거시경제 (글로벌) | 연준 동향, 금리, CPI, 달러 인덱스, 유가 | Reuters RSS, Bloomberg RSS |
| 거시경제 (한국) | 한국은행, 기준금리, 환율 | 한국은행 RSS, 네이버 뉴스 |
| 암호화폐 시장 | 비트코인 도미넌스, 주요 규제, 온체인 이벤트 | CoinDesk RSS, CryptoSlate RSS |
| 내 포트폴리오 종목 | 보유 코인·주식 관련 뉴스만 필터링 | NewsAPI + 키워드 필터 |

#### 3-2. 리포트 구성

```
📊 [2026-04-11 오전 9시] 포트폴리오 모닝 리포트

━━━ 포트폴리오 요약 ━━━
총 평가금액: ₩12,345,678 (+1.23%)
전일 대비: +₩152,000

━━━ 거시경제 주요 뉴스 ━━━
1. [연준] 파월 의장 금리 동결 시사 — 인플레이션 목표 근접
   출처: Reuters | 원문: https://...

2. [환율] 원/달러 1,340원대 하락 — 달러 약세 지속
   출처: 한국은행 | 원문: https://...

━━━ 암호화폐 시장 ━━━
3. [BTC] 비트코인 ETF 순유입 사상 최고 경신
   출처: CoinDesk | 원문: https://...

━━━ 내 종목 뉴스 ━━━
4. [BTC] 마이크로스트래티지 추가 매입 발표
   출처: CryptoSlate | 원문: https://...

5. [ETH] 이더리움 다음 업그레이드 일정 확정
   출처: Decrypt | 원문: https://...

━━━ 오늘의 주목 지표 ━━━
- 비트코인 도미넌스: 52.3%
- 공포·탐욕 지수: 72 (탐욕)
- 원/달러 환율: 1,342.50원
```

#### 3-3. 전송 방식 — Telegram Bot (추천)

- 이메일보다 모바일 친화적, 즉시 알림
- `python-telegram-bot` 라이브러리 사용
- 개인 채팅방에 Bot 추가 → Chat ID 발급 → `.env`에 저장
- 서버에서 매일 09:00 KST에 APScheduler가 발송

#### 3-4. 뉴스 수집 파이프라인

```
APScheduler (08:50 KST)
  → RSS 피드 파싱 (feedparser)
  → NewsAPI 키워드 검색 (보유 종목명)
  → 중복 제거 + 관련도 필터링
  → DB 저장 (news_reports 테이블)
  → 리포트 텍스트 생성
  → Telegram 발송 (09:00 KST)
```

---

### Phase 4: 추가 추천 기능

#### 4-1. 가격 알림 (Price Alert)
- 특정 종목이 설정 가격 도달 시 Telegram 즉시 알림
- 예: "비트코인이 1억원 돌파 시 알림", "ETH가 3% 이상 급락 시 알림"
- 웹에서 알림 조건 설정 UI 제공
- 5분마다 가격 체크 APScheduler 작업

#### 4-2. 수익 실현 계산기 (Tax Helper)
- 한국 가상자산 세금: 연 250만원 공제 후 22% 분리과세 (2025년 기준)
- 보유 자산 매도 시 예상 세금 시뮬레이션
- "지금 다 팔면 세금이 얼마?" → 즉시 계산

#### 4-3. 리밸런싱 제안
- 목표 비중 설정 (예: BTC 40%, ETH 30%, 기타 30%)
- 현재 비중 vs 목표 비중 차이 표시
- "목표 비중 맞추려면 BTC ₩500,000 매도, ETH ₩300,000 매수" 제안

#### 4-4. 트레이드 저널
- 수동으로 매수/매도 기록 입력
- 매매 이유, 당시 시장 상황, 감정 메모 저장
- 나중에 "내 결정이 옳았나?" 복기 가능

#### 4-5. 시장 상황판 (Market Overview)
- 비트코인 도미넌스 위젯
- 공포·탐욕 지수 (Alternative.me API)
- 원/달러, 원/엔 환율 실시간
- KOSPI / KOSDAQ / S&P500 / 나스닥 지수
- VIX (공포 지수)

#### 4-6. 포트폴리오 스냅샷 공유
- 현재 포트폴리오 현황을 PNG 이미지로 생성 (`playwright` 또는 `pillow`)
- Telegram으로 이미지 공유 가능

---

### Phase 5: 키움증권 연동 (토큰 발급 후)

- 키움증권 Open API+ 또는 REST API 사용
- 국내주식 잔고 조회 → 자동 통합
- 주식 종목의 PER, PBR 등 네이버 금융 / FinanceDataReader로 보완
- 서비스 구조는 이미 `services/kiwoom.py`로 분리 예정이므로 플러그인 방식으로 추가

---

## 4. 기술 스택

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

## 5. 환경변수 (.env) 구조

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

## 6. 개발 우선순위 (추천 순서)

```
[즉시 시작]
Phase 0-1: JWT 인증 (모바일 접속 편의성)
Phase 0-3: Cloudflare Tunnel (핸드폰으로 고정 URL 접속)

[다음]
Phase 1:   포트폴리오 통계 (핵심 가치)
Phase 3:   매일 뉴스 리포트 (Telegram)

[이후]
Phase 2:   종목별 상세 정보 (PER, PSR 등)
Phase 4:   가격 알림, 리밸런싱

[나중에]
Phase 5:   키움증권 연동
```

---

## 7. Claude Code 활용 팁

개발 시 유용한 스킬/기능:

- **`/commit`** — 단계별 작업 완료 후 커밋 메시지 자동 생성
- **`/loop`** — 서버 로그 모니터링, 반복 테스트 자동화
- **`claude-api` skill** — 뉴스 요약 기능에 Claude API 직접 통합 시 (출처 포함 한국어 요약)
- **`plan` subagent** — 복잡한 기능 설계 시 아키텍처 리뷰
- **Telegram Bot + APScheduler** 조합은 별도 인프라 없이 모바일 알림 구현 가능

---

## 8. 무료 API 목록

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
