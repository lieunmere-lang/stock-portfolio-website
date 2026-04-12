# Daily Change Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 보유현황 테이블의 "보유기간" 열을 "일일변동" 열로 교체하여 업비트 전일 대비 변동을 표시한다.

**Architecture:** 업비트 ticker API 응답에 이미 포함된 `signed_change_price`/`signed_change_rate`를 백엔드에서 프론트로 전달하고, 프론트에서 해당 데이터를 테이블 열로 표시한다.

**Tech Stack:** Python (FastAPI), 바닐라 JS/HTML

---

### Task 1: 업비트 서비스에서 변동 데이터 추가

**Files:**
- Modify: `backend/services/upbit.py:73-81` (일반 자산 result.append)
- Modify: `backend/services/upbit.py:94-102` (스테이킹 자산 result.append)

- [ ] **Step 1: 일반 자산 반환 dict에 변동 필드 추가**

`backend/services/upbit.py`의 일반 ��산 `result.append` (line 73-81)를 수정:

```python
        result.append(
            {
                "name": currency,
                "ticker": market,
                "quantity": float(asset["balance"]),
                "avg_price": float(asset["avg_buy_price"]),
                "current_price": float(price_info["trade_price"]),
                "signed_change_price": float(price_info["signed_change_price"]),
                "signed_change_rate": float(price_info["signed_change_rate"]),
            }
        )
```

- [ ] **Step 2: 스테이킹 자산 반환 dict에 변동 필드 추가**

`backend/services/upbit.py`의 스테이킹 자산 `result.append` (line 94-102)를 수정:

```python
        result.append(
            {
                "name": info["display_name"],
                "ticker": info["ticker"],
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": float(price_info["trade_price"]),
                "signed_change_price": float(price_info["signed_change_price"]),
                "signed_change_rate": float(price_info["signed_change_rate"]),
            }
        )
```

- [ ] **Step 3: 커밋**

```bash
git add backend/services/upbit.py
git commit -m "feat(upbit): include signed_change_price and signed_change_rate in asset data"
```

---

### Task 2: 스케줄러에서 변동 데이터를 캐시에 전달

**Files:**
- Modify: `backend/scheduler.py:180-202` (asset_rows 빌드 루프)
- Modify: `backend/scheduler.py:147-174` (수동 자산 병합)

- [ ] **Step 1: asset_rows에 변동 필드 추가**

`backend/scheduler.py`의 `for a in raw_assets:` 루프 내 `asset_rows.append` (line 190-202)를 수정:

```python
        asset_rows.append(
            {
                "name": a["name"],
                "ticker": a["ticker"],
                "quantity": qty,
                "avg_price": avg,
                "current_price": cur,
                "total_value": val,
                "profit_loss": pl,
                "profit_loss_rate": plr,
                "asset_type": a.get("asset_type", "crypto"),
                "signed_change_price": a.get("signed_change_price", 0),
                "signed_change_rate": a.get("signed_change_rate", 0),
            }
        )
```

- [ ] **Step 2: 수동 자산에도 변동 데이터 전달**

`backend/scheduler.py`의 수동 자산 가격 조회 부분 (line 153-162)을 수정. 현재 `manual_price_map`은 `trade_price`만 저장하는데, ticker 응답 전체를 저장하도록 변경:

```python
            manual_price_map = {t["market"]: t for t in price_res.json()}
```

수동 자산 루프 (line 164-174)에서 가격과 변동 데이터를 모두 꺼내도록 수정:

```python
        for m in manual_assets:
            ticker_data = manual_price_map.get(m.price_ticker)
            if ticker_data:
                cur_price = float(ticker_data["trade_price"])
                raw_assets.append({
                    "name": m.name,
                    "ticker": m.ticker,
                    "quantity": m.quantity,
                    "avg_price": m.avg_price,
                    "current_price": cur_price,
                    "first_purchase_date": m.first_purchase_date,
                    "signed_change_price": float(ticker_data["signed_change_price"]),
                    "signed_change_rate": float(ticker_data["signed_change_rate"]),
                })
```

- [ ] **Step 3: 커밋**

```bash
git add backend/scheduler.py
git commit -m "feat(scheduler): pass daily change data through to portfolio cache"
```

---

### Task 3: 프론트엔드 테이블 열 교체

**Files:**
- Modify: `frontend/index.html` (테이블 헤더 `<th>`, `renderHoldingsTable` 함수)

- [ ] **Step 1: 테이블 헤더 변경**

`frontend/index.html`의 `<thead>` 마지막 `<th>`:

변경 전:
```html
<th class="num">보유기간</th>
```

변경 후:
```html
<th class="num">일일변동</th>
```

- [ ] **Step 2: renderHoldingsTable에서 보유기간 코드 제거, 일일변동 추가**

`renderHoldingsTable` 함수에서:

1. `holdDays`, `holdText`, `first_purchase_date` 관련 코드 삭제:
```javascript
        // 아래 코드 전부 삭제
        const holdDays = a.first_purchase_date
            ? Math.floor((Date.now() - new Date(a.first_purchase_date)) / 86400000)
            : null;
        const holdText = holdDays != null
            ? holdDays >= 30 ? `${Math.floor(holdDays/30)}개월` : `${holdDays}일`
            : '—';
```

2. `const tk = a.ticker;` 줄 아래에 일일변동 변수 추가:
```javascript
        const dailyCls = pnlClass(a.signed_change_price);
```

3. 마지막 td (보유기간)를 일일변동으로 교체:

변경 전:
```html
            <td class="num text-muted" style="font-size:.8rem;">${holdText}</td>
```

변경 후:
```html
            <td class="num ${dailyCls}" data-flash="${tk}:daily">
                <div>${KRW(a.signed_change_price)}</div>
                <div class="text-muted" style="font-size:.72rem;">${PCT(a.signed_change_rate)}</div>
            </td>
```

- [ ] **Step 3: 커밋**

```bash
git add frontend/index.html
git commit -m "feat(frontend): replace holding period column with daily change"
```
