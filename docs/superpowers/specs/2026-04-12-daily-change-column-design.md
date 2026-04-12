# Daily Change Column in Holdings Table

## Overview

보유현황 테이블에 "보유기간" 열을 제거하고 "일일변동" 열을 추가한다. 업비트 ticker API의 `signed_change_price`와 `signed_change_rate`를 활용하여 전일 대비 변동을 표시한다.

## 백엔드 변경

### services/upbit.py — fetch_upbit_assets()

반환 dict에 두 필드 추가:
- `signed_change_price`: 전일 대비 변동 금액 (float)
- `signed_change_rate`: 전일 대비 변동률 (float, 0.05 = 5%)

일반 자산과 스테이킹 자산 모두에 적용. `ticker_map`에서 `price_info`를 이미 가져오고 있으므로 추가 API 호출 없음.

### scheduler.py — sync_portfolio()

`asset_rows`에 `signed_change_price`와 `signed_change_rate` 필드를 그대로 전달.

수동 등록 자산(manual_assets)도 ticker API를 호출하고 있으므로 동일하게 해당 필드 추가. 가격 조회 시 현재 `trade_price`만 가져오는 부분을 확장하여 `signed_change_price`, `signed_change_rate`도 저장.

DB `AssetSnapshot`에는 저장하지 않음 (실시간 데이터이므로 메모리 캐시만).

## 프론트엔드 변경

### index.html — 테이블 헤더

`<th>` 마지막 열 "보유기간"을 "일일변동"으로 교체. 열 수 10개 유지.

### index.html — renderHoldingsTable()

각 행에서:
- 보유기간 관련 코드 제거: `holdDays`, `holdText` 변수, `first_purchase_date` 참조
- 마지막 td를 일일변동으로 교체:

```html
<td class="num ${dailyCls}" data-flash="${tk}:daily">
    <div>${KRW(a.signed_change_price)}</div>
    <div style="font-size:.72rem;">${PCT(a.signed_change_rate)}</div>
</td>
```

- `dailyCls`는 `pnlClass(a.signed_change_price)` 사용
- flash 대상: `data-flash="${tk}:daily"`

## 표시 형식

- 금액: `₩1,234,567` (KRW 포맷터)
- 비율: `+3.45%` (PCT 포맷터)
- 상승: `text-up` (초록), 하락: `text-down` (빨강)
