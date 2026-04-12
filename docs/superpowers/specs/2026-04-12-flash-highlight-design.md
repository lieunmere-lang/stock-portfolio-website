# Flash Highlight on Data Change

## Overview

60초 간격 자동 동기화(`setInterval(loadDashboard, 60_000)`) 시 값이 변경된 요소를 1초간 배경색 flash로 표시한다. 숫자 증가는 초록, 감소는 빨강, 비숫자 변경은 노란색.

## 대상 요소

`data-flash` 속성을 가진 모든 요소를 추적. 아래 영역에 적용:

| 영역 | 요소 예시 | data-flash 키 |
|------|-----------|---------------|
| 요약 카드 | 총 평가액, 총 손익, 오늘 손익, 투자원금 | `total-value`, `total-pl`, `today-pl`, `investment` |
| 기간수익률 | 1일~1년 pill | `return-1d`, `return-1w`, ... |
| 리스크 지표 | MDD, 변동성, 샤프, HHI | `risk-mdd`, `risk-vol`, `risk-sharpe`, `risk-hhi` |
| 보유현황 테이블 | 현재가, 평가금액, 손익, 수익률 | `{ticker}:current_price`, `{ticker}:total_value`, ... |
| Top5 기여 | 기여도 수치 | `top5-{ticker}` |
| 베타 | 베타 값 | `beta` |

## 동작 흐름

1. `loadDashboard()` 호출 **전** — `snapshotFlashTargets()` 실행
   - `document.querySelectorAll('[data-flash]')`로 모든 대상 수집
   - `Map<string, string>` (key → textContent) 저장
2. 기존 렌더링 로직 실행 (변경 없음)
3. 렌더링 **후** — `applyFlash(snapshot)` 실행
   - 새로운 `[data-flash]` 요소들을 순회
   - 이전 snapshot과 textContent 비교
   - 변경된 요소에 flash 클래스 부여

## 숫자 비교

```
parseNumeric(text):
  text에서 ₩, %, +, 쉼표, 공백 제거
  parseFloat() 시도
  실패 시 NaN 반환
```

- 이전/이후 모두 숫자 파싱 성공 → 증가면 `flash-up`, 감소면 `flash-down`
- 파싱 실패 또는 값이 같음 → 문자열 비교, 다르면 `flash-neutral`
- 문자열도 같으면 → flash 없음

## CSS

```css
@keyframes flash-fade {
  0%   { opacity: 1; }
  100% { opacity: 0; }
}
.flash-up {
  background: rgba(22,163,74,.18);
  animation: flash-fade 1s ease-out forwards;
}
.flash-down {
  background: rgba(220,38,38,.18);
  animation: flash-fade 1s ease-out forwards;
}
.flash-neutral {
  background: rgba(234,179,8,.18);
  animation: flash-fade 1s ease-out forwards;
}
```

`animationend` 이벤트로 클래스 자동 제거 (다음 비교를 위해).

## 테이블 처리

`renderHoldingsTable`은 `innerHTML`로 tbody를 통째로 교체하므로 렌더링 전 요소가 소멸한다. 이를 위해:

- 렌더링 전 snapshot은 `data-flash` 속성값(키)을 기준으로 Map에 저장 (DOM 참조 아님)
- 렌더링 후 새로 생성된 요소의 `data-flash` 키로 매칭
- ticker 기반 키: `{ticker}:{field}` 형태 (예: `KRW-BTC:current_price`)

## 변경 파일

- `frontend/index.html`
  - CSS: `@keyframes flash-fade` + `.flash-up`, `.flash-down`, `.flash-neutral` 추가
  - JS: `snapshotFlashTargets()`, `applyFlash()` 함수 추가
  - `loadDashboard()`: 전후에 snapshot/apply 호출 2줄 추가
  - 각 렌더 함수 HTML 출력부: 값 요소에 `data-flash="키"` 속성 추가

## 제약 사항

- 최초 로딩 시에는 snapshot이 비어있으므로 flash 없음 (의도된 동작)
- 차트(Chart.js)는 canvas이므로 flash 대상에서 제외
