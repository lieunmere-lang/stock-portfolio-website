# Flash Highlight Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 60초 자동 갱신 시 값이 변경된 요소에 1초간 배경 flash 효과를 보여준다 (상승=초록, 하락=빨강, 기타=노랑).

**Architecture:** `data-flash` 속성으로 추적 대상을 마킹하고, `loadDashboard()` 전후에 snapshot/비교 유틸을 호출하여 변경된 요소에 CSS 애니메이션 클래스를 부여한다.

**Tech Stack:** 바닐라 JS + CSS animations (추가 라이브러리 없음)

---

### Task 1: CSS 애니메이션 추가

**Files:**
- Modify: `frontend/index.html:10-145` (style 블록)

- [ ] **Step 1: flash 애니메이션 CSS 추가**

`frontend/index.html`의 `</style>` 닫는 태그 직전에 추가:

```css
/* Flash highlight on data change */
@keyframes flash-fade {
    0%   { background-color: var(--flash-color); }
    100% { background-color: transparent; }
}
.flash-up      { --flash-color: rgba(22,163,74,.18); animation: flash-fade 1s ease-out; }
.flash-down    { --flash-color: rgba(220,38,38,.18); animation: flash-fade 1s ease-out; }
.flash-neutral { --flash-color: rgba(234,179,8,.18); animation: flash-fade 1s ease-out; }
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "style: add flash highlight CSS animations"
```

---

### Task 2: snapshot/apply 유틸 함수 추가

**Files:**
- Modify: `frontend/index.html:446-451` (State 섹션 아래)

- [ ] **Step 1: 유틸 함수 작성**

`frontend/index.html`의 `let currentHistoryDays = 90;` 줄 바로 아래에 추가:

```javascript
// ── Flash highlight ──────────────────────────────────────────────────────────
function snapshotFlashTargets() {
    const map = new Map();
    document.querySelectorAll('[data-flash]').forEach(el => {
        map.set(el.getAttribute('data-flash'), el.textContent.trim());
    });
    return map;
}

function parseNumeric(text) {
    const cleaned = text.replace(/[₩,%+\s]/g, '').replace(/,/g, '');
    const num = parseFloat(cleaned);
    return isNaN(num) ? null : num;
}

function applyFlash(prevSnapshot) {
    document.querySelectorAll('[data-flash]').forEach(el => {
        const key = el.getAttribute('data-flash');
        const prev = prevSnapshot.get(key);
        const curr = el.textContent.trim();
        if (prev == null || prev === curr) return;

        const prevNum = parseNumeric(prev);
        const currNum = parseNumeric(curr);
        let cls;
        if (prevNum !== null && currNum !== null && prevNum !== currNum) {
            cls = currNum > prevNum ? 'flash-up' : 'flash-down';
        } else {
            cls = 'flash-neutral';
        }

        el.classList.remove('flash-up', 'flash-down', 'flash-neutral');
        // force reflow to restart animation if same class
        void el.offsetWidth;
        el.classList.add(cls);
    });
}

// auto-remove flash class after animation ends
document.addEventListener('animationend', e => {
    if (e.animationName === 'flash-fade') {
        e.target.classList.remove('flash-up', 'flash-down', 'flash-neutral');
    }
});
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: add snapshotFlashTargets and applyFlash utilities"
```

---

### Task 3: loadDashboard에 snapshot/apply 호출 삽입

**Files:**
- Modify: `frontend/index.html:857-902` (loadDashboard 함수)

- [ ] **Step 1: loadDashboard 수정**

`loadDashboard()` 함수의 `try {` 바로 아래, `const [portfolio, analytics]` 앞에 snapshot 호출 추가:

```javascript
const flashSnap = snapshotFlashTargets();
```

`loadBeta();` 줄 바로 아래에 apply 호출 추가:

```javascript
applyFlash(flashSnap);
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: wire flash snapshot/apply into loadDashboard"
```

---

### Task 4: 요약 카드에 data-flash 속성 추가

**Files:**
- Modify: `frontend/index.html:468-499` (renderSummaryCards 함수)

- [ ] **Step 1: renderSummaryCards 내 요소에 data-flash 추가**

각 `textContent` 설정 줄 **앞에** `data-flash` 속성을 세팅하는 코드를 추가. 기존 getElementById로 가져온 요소에 setAttribute:

`renderSummaryCards` 함수의 기존 코드를 다음과 같이 수정:

```javascript
function renderSummaryCards(portfolio, analytics) {
    // 총 평가금액
    const tvEl = document.getElementById('card-total-value');
    tvEl.setAttribute('data-flash', 'total-value');
    tvEl.textContent = KRW(portfolio.total_value);

    // 총 손익
    const pl = portfolio.total_profit_loss;
    const plr = portfolio.total_profit_loss_rate;
    const plEl = document.getElementById('card-total-pl');
    plEl.setAttribute('data-flash', 'total-pl');
    plEl.textContent = KRW(pl);
    plEl.className = `fw-bold fs-4 mt-1 ${pnlClass(pl)}`;
    const plrEl = document.getElementById('card-total-plr');
    plrEl.setAttribute('data-flash', 'total-plr');
    plrEl.textContent = PCT(plr);
    plrEl.className = `fw-semibold ${pnlClass(plr)}`;
    const plIcon = document.getElementById('card-pl-icon');
    plIcon.className = `icon-badge ${pl >= 0 ? 'bg-up-soft' : 'bg-down-soft'}`;
    plIcon.innerHTML = `<i class="bi ${pl >= 0 ? 'bi-graph-up-arrow' : 'bi-graph-down-arrow'} fs-5"></i>`;

    // 오늘의 손익
    const tdPl = portfolio.today_profit_loss;
    const tdEl = document.getElementById('card-today-pl');
    tdEl.setAttribute('data-flash', 'today-pl');
    if (tdPl != null) {
        tdEl.textContent = KRW(tdPl);
        tdEl.className = `fw-bold fs-4 mt-1 ${pnlClass(tdPl)}`;
        const todayIcon = document.getElementById('card-today-icon');
        todayIcon.className = `icon-badge ${tdPl >= 0 ? 'bg-up-soft' : 'bg-down-soft'}`;
    } else {
        tdEl.textContent = '첫 동기화 후 표시';
        tdEl.className = 'fw-bold fs-5 mt-1 text-muted';
    }

    // 투자 원금
    const invEl = document.getElementById('card-investment');
    invEl.setAttribute('data-flash', 'investment');
    invEl.textContent = KRW(portfolio.total_investment);
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: add data-flash to summary card elements"
```

---

### Task 5: 기간수익률에 data-flash 속성 추가

**Files:**
- Modify: `frontend/index.html:501-515` (renderPeriodReturns 함수)

- [ ] **Step 1: renderPeriodReturns의 pill 요소에 data-flash 추가**

innerHTML 템플릿의 `<span class="period-pill ...">` 에 `data-flash` 속성 추가:

```javascript
function renderPeriodReturns(pr) {
    const labels = { '1d': '1일', '1w': '1주', '1m': '1개월', '3m': '3개월', '6m': '6개월', '1y': '1년' };
    const container = document.getElementById('period-returns-row');
    container.innerHTML = '';
    for (const [key, label] of Object.entries(labels)) {
        const val = pr[key];
        const cls = val == null ? '' : val >= 0 ? 'up' : 'down';
        const txt = val == null ? '—' : PCT(val, 2);
        container.innerHTML += `
            <div class="d-flex flex-column align-items-center gap-1">
                <span class="text-muted" style="font-size:.68rem;font-weight:600;">${label}</span>
                <span class="period-pill ${cls}" data-flash="return-${key}">${txt}</span>
            </div>`;
    }
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: add data-flash to period return pills"
```

---

### Task 6: 리스크 지표에 data-flash 속성 추가

**Files:**
- Modify: `frontend/index.html:517-546` (renderRiskMetrics 함수)

- [ ] **Step 1: 리스크 지표 요소에 data-flash 추가**

각 getElementById 호출 후 setAttribute 추가:

```javascript
function renderRiskMetrics(risk) {
    const mdd = risk.mdd;
    const mddEl = document.getElementById('risk-mdd');
    mddEl.setAttribute('data-flash', 'risk-mdd');
    mddEl.textContent = mdd != null ? PCT(mdd, 2) : '데이터 부족';
    mddEl.className = `fw-bold fs-5 mt-1 ${mdd != null ? 'text-down' : 'text-muted'}`;

    const vol = risk.volatility;
    const volEl = document.getElementById('risk-vol');
    volEl.setAttribute('data-flash', 'risk-vol');
    volEl.textContent = vol != null ? PCT(vol, 2) : '데이터 부족';
    volEl.className = `fw-bold fs-5 mt-1 ${vol != null ? '' : 'text-muted'}`;

    const sharpe = risk.sharpe;
    const sharpeEl = document.getElementById('risk-sharpe');
    sharpeEl.setAttribute('data-flash', 'risk-sharpe');
    if (sharpe != null) {
        sharpeEl.textContent = sharpe.toFixed(2);
        sharpeEl.className = `fw-bold fs-5 mt-1 ${sharpe >= 1 ? 'text-up' : sharpe >= 0 ? '' : 'text-down'}`;
    } else {
        sharpeEl.textContent = '데이터 부족';
        sharpeEl.className = 'fw-bold fs-5 mt-1 text-muted';
    }

    const hhi = risk.hhi;
    const hhiEl = document.getElementById('risk-hhi');
    hhiEl.setAttribute('data-flash', 'risk-hhi');
    hhiEl.textContent = hhi != null ? Math.round(hhi).toLocaleString() : '—';
    const hhiPct = Math.min((hhi / 10000) * 100, 100);
    const hhiColor = hhi > 2500 ? '#dc2626' : hhi > 1500 ? '#f59e0b' : '#16a34a';
    const hhiFill = document.getElementById('hhi-fill');
    hhiFill.style.width = `${hhiPct}%`;
    hhiFill.style.background = hhiColor;
    hhiEl.style.color = hhiColor;
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: add data-flash to risk metric elements"
```

---

### Task 7: 보유현황 테이블에 data-flash 속성 추가

**Files:**
- Modify: `frontend/index.html:548-597` (renderHoldingsTable 함수)

- [ ] **Step 1: 테이블 td에 ticker 기반 data-flash 키 추가**

`renderHoldingsTable`의 `tr.innerHTML` 템플릿 내 변동 가능 셀에 `data-flash` 추가:

```javascript
function renderHoldingsTable(assets) {
    const total = assets.reduce((s, a) => s + a.total_value, 0) || 1;
    const tbody = document.getElementById('holdings-tbody');
    tbody.innerHTML = '';
    if (!assets.length) {
        tbody.innerHTML = '<tr><td colspan="10" class="text-center py-5 text-muted">보유 종목 없음</td></tr>';
        return;
    }
    assets.forEach(a => {
        const pnl = a.profit_loss;
        const cls = pnlClass(pnl);
        const weight = (a.total_value / total * 100).toFixed(1);
        const purchase = a.quantity * a.avg_price;
        const holdDays = a.first_purchase_date
            ? Math.floor((Date.now() - new Date(a.first_purchase_date)) / 86400000)
            : null;
        const holdText = holdDays != null
            ? holdDays >= 30 ? `${Math.floor(holdDays/30)}개월` : `${holdDays}일`
            : '—';
        const tk = a.ticker;

        const tr = document.createElement('tr');
        tr.style.cursor = 'pointer';
        tr.addEventListener('click', () => {
            window.location.href = `/detail.html?ticker=${encodeURIComponent(a.ticker)}`;
        });
        tr.innerHTML = `
            <td>
                <div class="fw-semibold">${a.name}</div>
                <div class="text-muted" style="font-size:.72rem;">${a.ticker}</div>
            </td>
            <td class="num">${KRW(a.avg_price)}</td>
            <td class="num" data-flash="${tk}:price">${KRW(a.current_price)}</td>
            <td class="num">${NUM(a.quantity)}</td>
            <td class="num">${KRW(purchase)}</td>
            <td class="num fw-semibold" data-flash="${tk}:value">${KRW(a.total_value)}</td>
            <td class="num ${cls}" data-flash="${tk}:pnl">${KRW(pnl)}</td>
            <td class="num ${cls} fw-semibold" data-flash="${tk}:pnlr">${PCT(a.profit_loss_rate)}</td>
            <td class="num">
                <div class="d-flex align-items-center gap-1 justify-content-end">
                    <span data-flash="${tk}:weight">${weight}%</span>
                    <div style="width:40px;height:5px;border-radius:3px;background:#e2e8f0;overflow:hidden;">
                        <div style="width:${weight}%;height:100%;background:#3b82f6;border-radius:3px;"></div>
                    </div>
                </div>
            </td>
            <td class="num text-muted" style="font-size:.8rem;">${holdText}</td>
        `;
        tbody.appendChild(tr);
    });
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: add data-flash to holdings table cells"
```

---

### Task 8: Top5 기여도에 data-flash 속성 추가

**Files:**
- Modify: `frontend/index.html:648-678` (renderTop5 함수)

- [ ] **Step 1: Top5 수익 금액에 data-flash 추가**

`renderTop5`의 innerHTML 템플릿에서 수익 금액 span에 `data-flash` 추가:

```javascript
function renderTop5(top5) {
    const container = document.getElementById('top5-list');
    container.innerHTML = '';
    if (!top5.length) {
        container.innerHTML = '<p class="text-muted" style="font-size:.8rem;">데이터 없음</p>';
        return;
    }
    const maxPl = Math.max(...top5.map(t => Math.abs(t.profit_loss)), 1);
    top5.forEach((item, i) => {
        const cls = pnlClass(item.profit_loss);
        const barW = Math.abs(item.profit_loss) / maxPl * 100;
        const barColor = item.profit_loss >= 0 ? '#16a34a' : '#dc2626';
        container.innerHTML += `
            <div class="d-flex align-items-center gap-2 mb-3">
                <span class="text-muted fw-semibold" style="width:18px;font-size:.75rem;">${i+1}</span>
                <div class="flex-grow-1">
                    <div class="d-flex justify-content-between align-items-center">
                        <span class="fw-semibold" style="font-size:.82rem;">${item.ticker.replace('KRW-','')}</span>
                        <span class="${cls} fw-semibold" style="font-size:.8rem;" data-flash="top5-${item.ticker}:pl">${KRW(item.profit_loss)}</span>
                    </div>
                    <div style="height:4px;border-radius:2px;background:#e2e8f0;margin-top:4px;overflow:hidden;">
                        <div style="width:${barW}%;height:100%;background:${barColor};border-radius:2px;"></div>
                    </div>
                    <div class="d-flex justify-content-between">
                        <span class="text-muted" style="font-size:.68rem;">비중 ${(item.weight*100).toFixed(1)}%</span>
                        <span class="${cls}" style="font-size:.68rem;" data-flash="top5-${item.ticker}:plr">${PCT(item.profit_loss_rate)}</span>
                    </div>
                </div>
            </div>`;
    });
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: add data-flash to top5 contributor elements"
```

---

### Task 9: 베타에 data-flash 속성 추가

**Files:**
- Modify: `frontend/index.html:839-854` (loadBeta 함수)

- [ ] **Step 1: loadBeta에서 beta 요소에 data-flash 추가**

`loadBeta` 함수 내 `document.getElementById('card-beta')` 호출 후 setAttribute 추가. 기존 코드에서 `card-beta`를 참조하는 모든 곳에서 첫 번째 참조 전에 한 번만:

```javascript
async function loadBeta() {
    try {
        const data = await apiFetch('/api/analytics/beta');
        const betaEl = document.getElementById('card-beta');
        betaEl.setAttribute('data-flash', 'beta');
        betaEl.textContent = data.portfolio_beta.toFixed(3);
        betaEl.className = 'fw-bold fs-4 mt-1';
    } catch (e) {
        const betaEl = document.getElementById('card-beta');
        betaEl.setAttribute('data-flash', 'beta');
        betaEl.textContent = '오류';
        betaEl.className = 'fw-bold fs-4 mt-1 text-muted';
    }
}
```

- [ ] **Step 2: 커밋**

```bash
git add frontend/index.html
git commit -m "feat: add data-flash to beta card element"
```

---

### Task 10: 브라우저 수동 테스트

- [ ] **Step 1: 개발 서버 시작**

```bash
./manage_server.sh start
```

- [ ] **Step 2: 브라우저에서 확인**

`http://localhost:8000` 접속 후:
1. 첫 로딩 시 flash 없음 확인
2. 60초 대기 후 자동 갱신 시 변경된 값에 flash 효과 확인
3. 상승 값에 초록 배경, 하락 값에 빨강 배경, 비숫자 변경에 노란 배경 확인
4. flash가 1초 후 사라지는지 확인
5. 연속 갱신 시 flash가 매번 정상 재생되는지 확인

- [ ] **Step 3: 최종 커밋 (필요 시)**

테스트 중 수정사항이 있으면 커밋.
