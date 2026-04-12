# Phase 2: 종목별 상세 정보 — 설계 문서

> 작성일: 2026-04-12

## 목표

보유 종목(코인 + 미국 주식) 클릭 시 상세 정보를 통합 상세 페이지에서 제공한다.
대시보드에 보유 주식의 다가오는 실적 발표 일정을 표시한다.

## 범위

| 항목 | 설명 | 상태 |
|------|------|------|
| 2-1. 코인 상세 | CoinGecko 기반 시장 데이터, 보유현황, 가격차트, 링크 | 구현 완료 |
| 2-2. 주식 상세 | yfinance 기반 밸류에이션, 수익성, 배당, 시장 데이터, 애널리스트 컨센서스 | 신규 |
| 2-3. 통합 상세 페이지 | `detail.html`을 코인/주식 공용으로 확장. 자산 타입에 따라 적절한 섹션 표시 | 리팩터링 |
| 2-4. 어닝 캘린더 | 대시보드에 "다가오는 실적 발표" 카드 | 신규 |

### 범위 밖

- 주식 보유 정보 웹 등록 UI (불필요)
- 보유하지 않은 종목 검색/워치리스트
- 한국 주식 (미국 주식만 대상)
- 네이버 금융 스크래핑 (불필요)

---

## 아키텍처

### 데이터 소스

| 자산 타입 | 상세 데이터 | 가격 히스토리 |
|-----------|-------------|---------------|
| 코인 | CoinGecko API (기존) | 업비트 캔들 API (기존) |
| 주식 | yfinance | yfinance |

### 백엔드 신규 파일

- `backend/services/stock.py` — yfinance 래퍼. 종목 상세 조회, 가격 히스토리, 어닝 날짜 조회
- `backend/routers/stock.py` — 주식 상세 API 엔드포인트

### API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| GET | `/api/stock/{ticker}` | 주식 상세 정보 (밸류에이션, 수익성, 배당, 시장 데이터, 컨센서스) |
| GET | `/api/stock/{ticker}/price-history?days=N` | 주식 가격 히스토리 (차트용) |
| GET | `/api/earnings-calendar` | 보유 주식 어닝 캘린더 (다가오는 실적 발표 목록) |

### 캐싱

- 주식 상세 데이터: 메모리 캐시, TTL 15분 (yfinance 데이터 자체가 15분 지연)
- 어닝 캘린더: 메모리 캐시, TTL 6시간 (자주 바뀌지 않음)
- 가격 히스토리: 요청 시 조회, 캐시 없음 (yfinance가 자체 캐싱)

---

## 주식 상세 페이지 섹션

### 헤더

| 항목 | yfinance 필드 |
|------|---------------|
| 종목명 | `shortName` |
| 티커 | `symbol` |
| 현재가 (USD) | `currentPrice` |
| 당일 등락 (금액 + %) | `currentPrice - previousClose`, `(변동/previousClose)*100` |
| 시간외 가격 | `postMarketPrice` (장 마감 후) |

### 내 보유 현황

코인 상세와 동일한 레이아웃. DB의 주식 보유 정보(수량, 매수가) 기반.

| 항목 | 설명 |
|------|------|
| 평가금액 | 현재가 x 수량 (USD + KRW 환산) |
| 손익 | 평가금액 - 투자금액 |
| 수익률 | 손익 / 투자금액 x 100 |
| 수량 | 보유 주수 |
| 평균 매수가 | USD |
| 비중 | 전체 포트폴리오 대비 % |
| 투자금액 | 매수가 x 수량 |

### 밸류에이션

| 항목 | yfinance 필드 |
|------|---------------|
| PER | `trailingPE` |
| Forward PER | `forwardPE` |
| PBR | `priceToBook` |
| PSR | `priceToSalesTrailing12Months` |
| EV/EBITDA | `enterpriseToEbitda` |

### 수익성 / 배당

| 항목 | yfinance 필드 |
|------|---------------|
| ROE | `returnOnEquity` |
| ROA | `returnOnAssets` |
| 배당수익률 | `dividendYield` |
| 연간 배당금 | `dividendRate` |
| 배당일 | `exDividendDate` |

### 시장 데이터

| 항목 | yfinance 필드 | 비고 |
|------|---------------|------|
| 거래량 | `volume` | |
| 평균 거래량 | `averageVolume` | |
| Day Range | `dayLow` ~ `dayHigh` | 미니바 차트로 현재가 위치 표시 |
| 52주 Range | `fiftyTwoWeekLow` ~ `fiftyTwoWeekHigh` | 미니바 차트로 현재가 위치 표시 |
| 시가총액 | `marketCap` | |
| 52주 고가 | `fiftyTwoWeekHigh` | |
| 52주 저가 | `fiftyTwoWeekLow` | |

### 애널리스트 컨센서스

| 항목 | yfinance 필드 |
|------|---------------|
| 목표가 (평균) | `targetMeanPrice` |
| 목표가 (최저~최고) | `targetLowPrice` ~ `targetHighPrice` |
| 추천 등급 | `recommendationKey` (buy/hold/sell 등) |
| 추천 수 | `numberOfAnalystOpinions` |

### 가격 차트

코인과 동일한 UX. yfinance `history()` 메서드로 1개월/3개월/6개월/1년 기간별 조회.

### 링크

| 항목 | yfinance 필드 |
|------|---------------|
| 공식 사이트 | `website` |

---

## 통합 상세 페이지 (`detail.html`)

### URL 설계

- 코인: `detail.html?type=coin&ticker=KRW-BTC`
- 주식: `detail.html?type=stock&ticker=AAPL`
- 기존 URL(`detail.html?ticker=KRW-BTC`)은 하위호환을 위해 type 미지정 시 코인으로 간주

### 공통 섹션 (코인/주식 공유)

- 헤더 (종목명, 티커, 현재가, 등락)
- 내 보유 현황
- 가격 차트

### 자산 타입별 섹션

| 코인 전용 | 주식 전용 |
|-----------|-----------|
| 시가총액 (KRW) | 밸류에이션 (PER/PBR/PSR/EV-EBITDA) |
| 유통/전체 공급량 | 수익성/배당 (ROE/ROA/배당률) |
| 도미넌스 | 시장 데이터 (거래량, Day Range, 52W Range) |
| ATH | 애널리스트 컨센서스 |
| 백서 링크 | |

### 구현 방식

`detail.html` 내에서 `type` 파라미터에 따라:
1. 다른 API 호출 (`/api/coin/` vs `/api/stock/`)
2. 다른 렌더 함수 호출 (공통 함수 + 타입별 함수)
3. 코인 전용 / 주식 전용 DOM 섹션을 show/hide

---

## 어닝 캘린더 (대시보드)

### 위치

대시보드(`index.html`) 보유현황 테이블 아래, 자산배분 차트 위에 배치.

### 표시 내용

| 컬럼 | 설명 |
|------|------|
| 종목 | 티커 + 종목명 |
| 실적 발표일 | 날짜 (D-day 표시) |
| 예상 EPS | 컨센서스 예상 EPS (있을 경우) |

- 향후 90일 이내 실적 발표 예정인 보유 종목만 표시
- 발표일이 가까운 순으로 정렬
- 발표일이 7일 이내면 강조 표시
- 보유 주식이 없거나 예정된 어닝이 없으면 섹션 숨김

### 데이터 소스

yfinance `Ticker.calendar` 속성에서 어닝 날짜 추출. 보유 주식 목록은 DB에서 조회.

---

## 대시보드 보유현황 테이블 확장

기존 보유현황 테이블에 주식도 함께 표시. 코인과 주식을 구분하는 "타입" 뱃지 추가 (또는 섹션 분리).

- 주식 행 클릭 시 `detail.html?type=stock&ticker=AAPL`로 이동
- 주식 가격은 USD 표시 + KRW 환산
- 환율: yfinance `USDKRW=X` 티커로 조회, 스케줄러에서 1시간 간격 캐시 갱신

---

## 주식 보유 데이터 모델

기존 `ManualAsset` 테이블 활용 또는 별도 테이블. 필드:

| 필드 | 타입 | 설명 |
|------|------|------|
| ticker | str | 미국 주식 티커 (예: AAPL) |
| name | str | 종목명 |
| quantity | float | 보유 수량 |
| avg_price | float | 평균 매수가 (USD) |
| currency | str | USD (고정) |
| asset_type | str | stock |
| first_purchase_date | date | 최초 매수일 |
| is_active | bool | 활성 여부 |

---

## 에러 처리

- yfinance 조회 실패 시: 캐시된 데이터 반환, 캐시도 없으면 에러 메시지
- 존재하지 않는 티커: 404 응답
- yfinance 레이트 리밋: 요청 간 최소 간격 유지 (100ms)
