# Phase 3: 뉴스 리포트 UI 개선 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 매일 생성되는 뉴스 리포트를 효과적으로 탐색할 수 있도록 리스트 뷰, 대시보드 미리보기, 페이지네이션을 추가한다.

**Architecture:** 백엔드 `/api/news/reports`에 offset/limit 페이지네이션 추가. `news.html`에 리포트 뷰/리스트 뷰 토글 추가. `index.html` 대시보드에 뉴스 미리보기 카드 삽입.

**Tech Stack:** Python/FastAPI (백엔드), 바닐라 HTML/CSS/JS + Bootstrap 5 (프론트엔드)

**Spec:** `docs/superpowers/specs/2026-04-12-phase3-news-ui-improvements.md`

---

### Task 1: 백엔드 — `/api/news/reports` 페이지네이션

**Files:**
- Modify: `backend/routers/news.py:297-300`

- [ ] **Step 1: `/api/news/reports` 엔드포인트에 offset/limit 파라미터 추가**

`backend/routers/news.py`의 `list_reports` 함수를 다음과 같이 변경한다:

```python
@router.get("/reports")
def list_reports(
    offset: int = 0,
    limit: int = 10,
    user: str = Depends(require_auth),
):
    """뉴스 리포트 목록 조회 (페이지네이션)"""
    total = len(MOCK_REPORTS_LIST)
    items = MOCK_REPORTS_LIST[offset : offset + limit]
    return {
        "items": items,
        "total": total,
        "has_more": offset + limit < total,
    }
```

- [ ] **Step 2: 서버 시작 후 수동 확인**

Run: `curl -s -H "Authorization: Bearer <token>" "http://localhost:8000/api/news/reports?offset=0&limit=2" | python3 -m json.tool`

Expected: `items` 배열에 2건, `total`에 5, `has_more`가 `true`

- [ ] **Step 3: 커밋**

```bash
git add backend/routers/news.py
git commit -m "feat(backend): add pagination to /api/news/reports endpoint"
```

---

### Task 2: `news.html` — 뷰 토글 버튼 + 리스트 뷰 HTML/CSS

**Files:**
- Modify: `frontend/news.html:90-149` (CSS 추가)
- Modify: `frontend/news.html:215-230` (헤더 영역)
- Modify: `frontend/news.html:248-257` (리스트 뷰 HTML 추가)

- [ ] **Step 1: CSS 추가**

`frontend/news.html`의 `</style>` 직전 (149행 부근)에 리스트 뷰용 CSS를 추가한다:

```css
/* === List view === */
.view-toggle .btn { font-size: .82rem; padding: .3rem .75rem; }
.view-toggle .btn.active { background: #1d4ed8; color: #fff; border-color: #1d4ed8; }
.report-list-item {
    padding: 1rem 1.25rem;
    border-bottom: 1px solid #f1f5f9;
    cursor: pointer;
    transition: background .15s;
}
.report-list-item:last-child { border-bottom: none; }
.report-list-item:hover { background: #f8fafc; }
.report-list-date { font-weight: 700; font-size: .95rem; color: #1e293b; }
.report-list-meta { font-size: .72rem; color: #94a3b8; }
.report-list-preview {
    font-size: .85rem; color: #475569;
    overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
    max-width: 100%;
}
#btn-load-more {
    display: block; margin: 1rem auto;
    font-size: .85rem;
}
```

- [ ] **Step 2: 헤더에 뷰 토글 버튼 추가**

`frontend/news.html`의 헤더 영역 (215~230행)을 다음으로 교체한다:

```html
<!-- 헤더 + 뷰 토글 + 날짜 네비게이션 -->
<div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
    <div class="d-flex align-items-center gap-3">
        <h1 class="report-date-title mb-0">
            <i class="bi bi-newspaper text-primary"></i>
            <span id="header-report">모닝 리포트 — <span id="report-date">—</span></span>
            <span id="header-list" class="d-none">뉴스 리포트</span>
        </h1>
        <div class="view-toggle btn-group btn-group-sm">
            <button id="btn-view-report" class="btn btn-outline-secondary active">리포트</button>
            <button id="btn-view-list" class="btn btn-outline-secondary">목록</button>
        </div>
    </div>
    <div id="date-nav" class="date-nav d-flex align-items-center gap-2">
        <button id="btn-prev" class="btn btn-sm btn-outline-secondary" disabled>
            <i class="bi bi-chevron-left"></i> 이전
        </button>
        <button id="btn-next" class="btn btn-sm btn-outline-secondary" disabled>
            다음 <i class="bi bi-chevron-right"></i>
        </button>
    </div>
</div>
```

- [ ] **Step 3: 리스트 뷰 컨테이너와 더보기 버튼 HTML 추가**

`frontend/news.html`의 `<!-- 빈 상태 -->` 직전 (254행 부근)에 리스트 뷰 HTML을 추가한다:

```html
<!-- 리스트 뷰 -->
<div id="list-view" class="d-none">
    <div id="report-list" class="section-card bg-white"></div>
    <button id="btn-load-more" class="btn btn-sm btn-outline-secondary d-none">더보기</button>
</div>
```

- [ ] **Step 4: 커밋**

```bash
git add frontend/news.html
git commit -m "feat(frontend): add list view toggle and HTML structure to news page"
```

---

### Task 3: `news.html` — 리스트 뷰 JS 로직

**Files:**
- Modify: `frontend/news.html` (JS 섹션)

- [ ] **Step 1: 뷰 전환 + 리스트 로딩 + 더보기 JS 추가**

`frontend/news.html`의 `<script>` 내부, `// ── State` 섹션 (422행 부근) 이후의 state 변수와 함수들을 수정한다.

기존 state 변수에 리스트 뷰 state를 추가한다:

```javascript
// ── State ─────────────────────────────────────────────────────────────��──────
let reportsList = [];
let currentReportIndex = -1;
let currentView = 'report'; // 'report' | 'list'
let listOffset = 0;
const LIST_LIMIT = 10;
let listHasMore = false;
```

뷰 전환 함수를 추가한다:

```javascript
// ── View toggle ─────────────────────────────────────────────────────────────
function switchView(view) {
    currentView = view;
    const isReport = view === 'report';

    // Toggle active button
    document.getElementById('btn-view-report').classList.toggle('active', isReport);
    document.getElementById('btn-view-list').classList.toggle('active', !isReport);

    // Toggle header text
    document.getElementById('header-report').classList.toggle('d-none', !isReport);
    document.getElementById('header-list').classList.toggle('d-none', isReport);

    // Toggle sections
    document.getElementById('summary-card').classList.toggle('d-none', !isReport);
    document.getElementById('indicators-row').classList.toggle('d-none', !isReport);
    document.getElementById('news-sections').classList.toggle('d-none', !isReport);
    document.getElementById('date-nav').classList.toggle('d-none', !isReport);
    document.getElementById('list-view').classList.toggle('d-none', isReport);
    document.getElementById('empty-state').classList.add('d-none');

    if (!isReport) {
        listOffset = 0;
        document.getElementById('report-list').innerHTML = '';
        loadReportList();
    }
}
```

리스트 로딩 + 더보기 함수를 추가한다:

```javascript
// ── List view ───────────────────────────────────────────────────────────────
async function loadReportList() {
    try {
        const data = await apiFetch(`/api/news/reports?offset=${listOffset}&limit=${LIST_LIMIT}`);
        const container = document.getElementById('report-list');

        (data.items || []).forEach(item => {
            const div = document.createElement('div');
            div.className = 'report-list-item';
            div.innerHTML = `
                <div class="d-flex justify-content-between align-items-center mb-1">
                    <span class="report-list-date">${escapeHtml(item.report_date)}</span>
                    <span class="report-list-meta">수집 ${item.total_collected}건 → 선별 ${item.total_selected}건 · ${escapeHtml(item.model_used || '')}</span>
                </div>
                <div class="report-list-preview">${escapeHtml(item.summary_preview || '')}</div>
            `;
            div.addEventListener('click', () => {
                switchView('report');
                loadReport(item.report_date);
            });
            container.appendChild(div);
        });

        listOffset += (data.items || []).length;
        listHasMore = data.has_more;
        document.getElementById('btn-load-more').classList.toggle('d-none', !listHasMore);
    } catch (e) {
        console.error('load report list error:', e);
    }
}
```

- [ ] **Step 2: 이벤트 리스너 연결**

`DOMContentLoaded` 핸들러 (529행 부근) 안에 다음 리스너를 추가한다:

```javascript
document.getElementById('btn-view-report').addEventListener('click', () => switchView('report'));
document.getElementById('btn-view-list').addEventListener('click', () => switchView('list'));
document.getElementById('btn-load-more').addEventListener('click', loadReportList);
```

- [ ] **Step 3: 기존 `loadReportsList` 함수의 응답 형식 대응**

기존 `loadReportsList` 함수 (487행 부근)가 새 응답 형식(`{items, total, has_more}`)을 처리하도록 수정한다:

```javascript
async function loadReportsList() {
    try {
        const data = await apiFetch('/api/news/reports?offset=0&limit=100');
        reportsList = data.items || data;
    } catch(e) {
        console.error('load reports list error:', e);
        reportsList = [];
    }
    updateNavButtons();
}
```

- [ ] **Step 4: 브라우저에서 확인**

1. `/news.html` 접속
2. [목록] 버튼 클릭 → 리스트 뷰 전환 확인
3. 리스트 아이템 클릭 → 리포트 뷰 전환 + 해당 날짜 로드 확인
4. [리포트] 버튼 클릭 → 다시 리포트 뷰 전환 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/news.html
git commit -m "feat(frontend): add list view JS logic with load-more pagination"
```

---

### Task 4: `index.html` — 대시보드 뉴스 미리보기 카드

**Files:**
- Modify: `frontend/index.html:296-298` (HTML 추가)
- Modify: `frontend/index.html:1014-1056` (JS 함수 추가 + loadDashboard 수정)

- [ ] **Step 1: 뉴스 미리보기 카드 HTML 추가**

`frontend/index.html`의 요약 카드 `</div>` 닫힌 직후 (296행), `<!-- ② 수익률 분석 -->` 직전에 다음 HTML을 추가한다:

```html
    <!-- 뉴스 리포트 미리보기 -->
    <div id="news-preview" class="section-card bg-white p-4 mb-4 d-none">
        <div class="d-flex justify-content-between align-items-center mb-2">
            <div class="d-flex align-items-center gap-2">
                <div class="icon-badge" style="background:rgba(99,102,241,.12);color:#6366f1;">
                    <i class="bi bi-newspaper fs-5"></i>
                </div>
                <div>
                    <div class="text-muted" style="font-size:.72rem;font-weight:600;">오늘의 모닝 리포트</div>
                    <div id="news-preview-date" class="fw-semibold" style="font-size:.85rem;">—</div>
                </div>
            </div>
            <a href="/news.html" class="btn btn-sm btn-outline-primary">자세히 보기 <i class="bi bi-arrow-right"></i></a>
        </div>
        <p id="news-preview-summary" class="mb-2" style="font-size:.85rem;color:#475569;line-height:1.6;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;"></p>
        <div id="news-preview-items" class="mb-2"></div>
        <div id="news-preview-meta" class="text-muted" style="font-size:.72rem;"></div>
    </div>
```

- [ ] **Step 2: 뉴스 미리보기 로드 함수 추가**

`frontend/index.html`의 `<script>` 내부, `loadDashboard` 함수 직전에 다음 함수를 추가한다:

```javascript
// ── 뉴스 리포트 미리보기 ───────────────────────────────────��────────────────
async function loadNewsPreview() {
    try {
        const report = await apiFetch('/api/news/latest');
        if (!report || !report.report_date) return;

        const card = document.getElementById('news-preview');
        card.classList.remove('d-none');

        document.getElementById('news-preview-date').textContent = report.report_date;
        document.getElementById('news-preview-summary').textContent = report.summary || '';

        // 중요도 상위 3개 뉴스
        const topItems = (report.items || [])
            .sort((a, b) => (b.importance || 0) - (a.importance || 0))
            .slice(0, 3);

        const itemsHtml = topItems.map(item => {
            const dots = Array.from({length: 5}, (_, i) =>
                `<span style="display:inline-block;width:5px;height:5px;border-radius:50%;background:${i < item.importance ? '#f59e0b' : '#e2e8f0'};"></span>`
            ).join('');
            const ticker = item.related_ticker
                ? `<span style="font-size:.7rem;font-weight:600;padding:.1rem .35rem;border-radius:4px;background:rgba(22,163,74,.1);color:#16a34a;">${escapeHtml(item.related_ticker)}</span>`
                : '';
            return `<div class="d-flex align-items-center gap-2 mb-1" style="font-size:.82rem;">
                <span class="d-flex gap-1">${dots}</span>
                <span style="color:#334155;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${escapeHtml(item.title)}</span>
                ${ticker}
            </div>`;
        }).join('');
        document.getElementById('news-preview-items').innerHTML = itemsHtml;

        document.getElementById('news-preview-meta').textContent =
            `수집 ${report.total_collected}건 → 선별 ${report.total_selected}건`;
    } catch (e) {
        console.error('news preview error:', e);
        // 리포트 없으면 카드 숨김 유지
    }
}

function escapeHtml(str) {
    if (!str) return '';
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
```

- [ ] **Step 3: `loadDashboard`에서 뉴스 미리보기 호출**

`frontend/index.html`의 `loadDashboard` 함수 안에서 `loadMarketIndicators()` 호출 근처 (1054행 부근)에 `loadNewsPreview()` 호출을 추가한다:

```javascript
        loadMarketIndicators();  // 비동기 — 공포탐욕, 환율
        loadEarningsCalendar();  // 비동기 — 메인 로딩 블로킹 안함
        loadNewsPreview();       // 비동기 — 뉴스 리포트 미리보기
        applyFlash(flashSnap);
```

- [ ] **Step 4: 브라우저에서 확인**

1. `/` (대시보드) 접속
2. 요약 카드 아래에 뉴스 미리보기 카드 표시 확인
3. AI 요약 2줄 말줄임 확인
4. 상위 뉴스 3개 + 중요도 점 + 티커 뱃지 확인
5. "자세히 보기" 클릭 → `/news.html` 이동 확인

- [ ] **Step 5: 커밋**

```bash
git add frontend/index.html
git commit -m "feat(frontend): add news report preview card to dashboard"
```

---

### Task 5: `index.html` — `escapeHtml` 중복 방지 확인

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: 기존 `escapeHtml` 함수 존재 여부 확인**

`index.html`에 이미 `escapeHtml` 함수가 정의되어 있는지 검색한다. 이미 존재하면 Task 4에서 추가한 `escapeHtml` 정의를 제거한다. 존재하지 않으면 그대로 둔다.

Run: `grep -n "escapeHtml" frontend/index.html`

- [ ] **Step 2: 중복 시 제거 후 커밋 (해당 시에만)**

```bash
git add frontend/index.html
git commit -m "fix: remove duplicate escapeHtml function"
```

---

### Task 6: 통합 확인

**Files:** 없음 (수동 확인)

- [ ] **Step 1: 전체 플로우 확인**

1. 대시보드(`/`) 접속 → 뉴스 미리보기 카드 표시
2. "자세히 보기" 클릭 → `/news.html` 이동
3. 최신 리포트 표시 (리포트 뷰)
4. [목록] 버튼 클릭 → 리스트 뷰 전환, 10건 표시
5. 리스트 아이템 클릭 → 리포트 뷰로 전환 + 해당 날짜 로드
6. 이전/다음 버튼 → 리포트 있는 날짜만 이동 (빈 날짜 건너뜀)
7. [리포트] ↔ [목록] 반복 전환 시 깨짐 없는지 확인

- [ ] **Step 2: 최종 커밋 (필요 시)**

변경 사항이 있으면 커밋한다.
