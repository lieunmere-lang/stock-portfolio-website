# 시장 상황판 (Market Overview) 설계 스펙

## 개요

Finviz 스타일 트리맵 히트맵 + 시장 지표 위젯 카드로 구성된 시장 상황판 페이지.
포트폴리오 체크 전 시장 전체 분위기를 한눈에 파악하고, 내 자산과 시장 흐름의 관계를 이해하는 것이 목적.

## 페이지 구조

```
┌──────────────────────────────────────────────┐
│  기간 탭: [1일] [1주] [1개월] [YTD]          │
├──────────────────────────────────────────────┤
│                                              │
│           트리맵 히트맵                       │
│                                              │
│  ┌─────────────────────┬────────┬──────┐     │
│  │   미국주식 (S&P500) │  코인  │원자재│     │
│  │   GICS 섹터별 그룹  │ 상위5개│금은유│     │
│  └─────────────────────┴────────┴──────┘     │
│                                              │
├──────────────────────────────────────────────┤
│                                              │
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│
│  │공포탐욕 │ │USD/KRW │ │BTC.D   │ │VIX     ││
│  │35 Fear │ │1,382   │ │54.2%   │ │18.3    ││
│  │~~spark~~│ │~~spark~~│ │~~spark~~│ │~~spark~~││
│  └────────┘ └────────┘ └────────┘ └────────┘│
│  ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐│
│  │DXY     │ │US 10Y  │ │김치프리 │ │JPY/KRW ││
│  │104.5   │ │4.52%   │ │3.2%    │ │9.21    ││
│  │~~spark~~│ │~~spark~~│ │~~spark~~│ │~~spark~~││
│  └────────┘ └────────┘ └────────┘ └────────┘│
└──────────────────────────────────────────────┘
```

## 히트맵 상세

### 자산 그룹

| 섹터 | 범위 | 셀 크기 기준 | 색상 기준 |
|------|------|-------------|----------|
| 미국주식 | S&P500 전체 종목 | 시가총액 | 선택된 기간의 등락률 |
| 코인 | 시총 상위 5개 (BTC, ETH, XRP, SOL, BNB 등) | 시가총액 | 선택된 기간의 등락률 |
| 원자재 | 금, 은, WTI | 균등 | 선택된 기간의 등락률 |

### 색상 스케일

- 짙은 초록: +3% 이상
- 연한 초록: +1% ~ +3%
- 회색: -1% ~ +1%
- 연한 빨강: -1% ~ -3%
- 짙은 빨강: -3% 이하

### 셀 표시 내용

- 티커 심볼 (e.g., AAPL)
- 등락률 (e.g., +2.3%)
- 셀 크기가 충분하면 종목명도 표시

### 기간 선택 탭

- **1일**: 당일 등락률 (기본값)
- **1주**: 최근 1주 등락률
- **1개월**: 최근 1개월 등락률
- **YTD**: 연초 대비 등락률

### GICS 섹터 그룹 (미국주식)

S&P500 종목을 11개 GICS 섹터로 그룹화하여 표시:
Technology, Healthcare, Financial, Consumer Cyclical, Communication Services, Industrials, Consumer Defensive, Energy, Utilities, Real Estate, Basic Materials

각 섹터는 시각적으로 구분되는 영역으로 묶이고, 섹터 라벨이 표시됨.

## 위젯 카드 상세

### 위젯 목록 (8개, 4x2 그리드)

| 위젯 | 데이터 소스 | 표시 내용 |
|------|-----------|----------|
| 공포·탐욕 지수 | Alternative.me API | 수치 (0-100) + 라벨 (Extreme Fear ~ Extreme Greed) + 7일 스파크라인 |
| USD/KRW | yfinance (KRW=X) | 현재 환율 + 등락률 + 7일 스파크라인 |
| BTC 도미넌스 | CoinGecko API | 비율(%) + 등락 + 7일 스파크라인 |
| VIX | yfinance (^VIX) | 현재 수치 + 등락 + 7일 스파크라인 |
| DXY | yfinance (DX-Y.NYB) | 현재 수치 + 등락률 + 7일 스파크라인 |
| US 10Y 국채금리 | yfinance (^TNX) | 현재 금리(%) + 등락 + 7일 스파크라인 |
| 김치프리미엄 | 업비트 BTC가 / 바이낸스 BTC가 * USD/KRW 비교 계산 | 프리미엄(%) + 7일 스파크라인 |
| JPY/KRW | yfinance (JPYKRW=X) | 현재 환율 + 등락률 + 7일 스파크라인 |

### 스파크라인

- 최근 7일간 일봉 종가 기준 미니 라인차트
- 높이 28px, 너비 60px
- 색상: 양이면 초록, 음이면 빨강 (7일 전 대비)

## 데이터 흐름

### 데이터 갱신

- 페이지 로드 시 1회 fetch
- 자동 갱신 없음

### API 엔드포인트

새로운 라우터 `backend/routers/market.py` 추가:

```
GET /api/market/heatmap?period=1d
  → { stocks: [...], coins: [...], commodities: [...] }

GET /api/market/indicators
  → { fear_greed: {...}, usd_krw: {...}, btc_dominance: {...}, vix: {...}, dxy: {...}, us10y: {...}, kimchi_premium: {...}, jpy_krw: {...} }
```

### 히트맵 데이터 구조

```json
{
  "stocks": [
    {
      "ticker": "AAPL",
      "name": "Apple Inc.",
      "sector": "Technology",
      "market_cap": 3000000000000,
      "change_pct": 2.3
    }
  ],
  "coins": [
    {
      "ticker": "BTC",
      "name": "Bitcoin",
      "market_cap": 1200000000000,
      "change_pct": 4.1
    }
  ],
  "commodities": [
    {
      "ticker": "GC=F",
      "name": "금",
      "change_pct": 0.5
    }
  ]
}
```

### 위젯 데이터 구조

```json
{
  "fear_greed": { "value": 35, "label": "Fear", "sparkline": [28, 30, 32, 35, 33, 36, 35] },
  "usd_krw": { "value": 1382, "change_pct": 0.3, "sparkline": [1375, 1378, 1380, 1379, 1381, 1383, 1382] },
  "btc_dominance": { "value": 54.2, "change_pct": -0.5, "sparkline": [54.8, 54.6, 54.5, 54.3, 54.4, 54.1, 54.2] },
  "vix": { "value": 18.3, "change": -1.2, "sparkline": [20.1, 19.5, 19.8, 19.0, 18.7, 18.5, 18.3] },
  "dxy": { "value": 104.5, "change_pct": -0.2, "sparkline": [105.0, 104.8, 104.7, 104.6, 104.5, 104.4, 104.5] },
  "us10y": { "value": 4.52, "change": 0.03, "sparkline": [4.48, 4.50, 4.49, 4.51, 4.50, 4.53, 4.52] },
  "kimchi_premium": { "value": 3.2, "change_pct": 0.8, "sparkline": [2.1, 2.5, 2.8, 3.0, 2.9, 3.1, 3.2] },
  "jpy_krw": { "value": 9.21, "change_pct": -0.1, "sparkline": [9.25, 9.23, 9.22, 9.24, 9.22, 9.20, 9.21] }
}
```

## 프론트엔드

### 파일

- `frontend/market.html` — 시장 상황판 페이지 (기존 index.html, news.html과 동일한 레이아웃/사이드바 구조)

### 트리맵 렌더링

- 라이브러리: 별도 라이브러리 없이 CSS Grid + JS로 직접 구현하거나, 경량 트리맵 라이브러리 사용
  - 후보: D3.js treemap, Chart.js treemap 플러그인, 또는 순수 JS 구현
  - **권장: D3.js** — S&P500 전체 500개 종목의 정확한 트리맵 레이아웃 계산에 적합

### 사이드바 연동

- 현재 `시장 상황판 <준비중>` 링크를 활성화하여 `/market.html`로 연결

## 백엔드

### 데이터 소스

| 데이터 | 소스 | 비고 |
|--------|------|------|
| S&P500 종목 목록 + 섹터 | Wikipedia S&P500 테이블 or 하드코딩 | 분기별 수동 업데이트 |
| 주가 등락률 | yfinance | period에 따라 1d/5d/1mo/ytd |
| 코인 시세 | CoinGecko API | 시총 상위 5개 |
| 원자재 시세 | yfinance (GC=F, SI=F, CL=F) | 금, 은, WTI |
| 공포·탐욕 | Alternative.me API | 기존 사용 중 |
| 환율 | yfinance | KRW=X, JPYKRW=X |
| BTC 도미넌스 | CoinGecko /global | 전체 시장 대비 BTC 비율 |
| VIX, DXY, US10Y | yfinance | ^VIX, DX-Y.NYB, ^TNX |
| 김치프리미엄 | 업비트 BTC/KRW vs CoinGecko BTC/USD * USD/KRW | 계산 |

### 캐싱

- 히트맵 데이터: 메모리 캐시 (기존 scheduler.py의 `_cache` 패턴 활용)
- S&P500 종목 목록: 파일 또는 하드코딩 (자주 변경되지 않음)
- 위젯 스파크라인: 7일치 데이터를 1회 fetch, 캐시

### 성능 고려

- S&P500 전체 500종목 yfinance 호출은 배치 다운로드(`yf.download()`)로 한 번에 처리
- 페이지 로드 시 히트맵 + 위젯을 병렬로 fetch
- 응답 시간 목표: 5초 이내 (캐시 히트 시 즉시)

## 에러 처리

- API 실패 시 해당 섹터/위젯에 "데이터 없음" 표시
- 부분 실패 허용: 코인 API 실패해도 주식 히트맵은 표시
