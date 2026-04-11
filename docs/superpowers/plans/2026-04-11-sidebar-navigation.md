# 사이드바 네비게이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Phase 1 대시보드(`index.html`)와 Phase 2 코인 상세(`detail.html`)에 공통 반응형 사이드바를 도입하여, Phase 1 섹션 간 앵커 스크롤 내비게이션과 향후 Phase 3-5 페이지 확장을 지원한다.

**Architecture:** Bootstrap 5.3의 `.offcanvas-lg` 반응형 오프캔버스를 사용하여 데스크톱(≥992px)에서는 좌측 240px 고정 사이드바, 모바일(<992px)에서는 햄버거로 여는 슬라이드 오프캔버스를 동일 마크업으로 구현한다. Phase 1 섹션은 IntersectionObserver 기반 스크롤스파이로 활성 상태가 자동 갱신된다. 이번 스코프는 프론트엔드 두 HTML 파일만 수정하며 백엔드·DB·라우터에는 손대지 않는다.

**Tech Stack:**
- Bootstrap 5.3.3 (기존, offcanvas-lg 지원)
- Bootstrap Icons 1.11.3 (기존)
- Vanilla HTML/CSS/JS (기존, 번들러 없음)
- FastAPI StaticFiles로 서빙되는 `frontend/` 폴더

**Spec reference:** `docs/superpowers/specs/2026-04-11-sidebar-navigation-design.md`

**Testing approach:** 이 프로젝트엔 프론트엔드 자동 테스트 프레임워크가 없다. 각 태스크 후 `./manage_server.sh start`로 로컬 서버를 띄우고 브라우저에서 수동 검증한다. 자동 테스트는 범위 밖(Phase 1·2 구현 시에도 수동 검증만 사용됨).

**Critical discovery (pre-execution):**
- `frontend/detail.html`은 **Bootstrap JS 번들이 로드되지 않은 상태**로 배포되어 있다(line 10에 Chart.js만 있음). offcanvas 컴포넌트 사용에 `bootstrap.Offcanvas.getInstance()`가 필요하므로 detail.html에 `bootstrap.bundle.min.js`를 반드시 추가해야 한다. Task 5에 포함.
- `index.html`의 Phase 1 "리스크 지표"는 "수익률 분석"과 같은 카드 안에 **중첩**되어 있다(line 211-248). 이 때문에 IntersectionObserver 콜백에서 중첩된 여러 섹션이 동시에 `isIntersecting=true`가 되는 경우가 발생한다. 콜백에서 **문서 순서상 마지막으로 교차한 섹션**을 활성으로 선택하는 로직으로 해결한다(Task 4 참조). Spec의 "IntersectionObserver 사용" 결정은 유지하되, 콜백 로직만 정교하게 구현한다.

---

## File Structure

수정 파일:

| 파일 | 역할 | 변경 유형 |
|------|------|-----------|
| `frontend/index.html` | Phase 1 대시보드 | Modify: 섹션 id 추가, navbar 축소, 사이드바 HTML/CSS/JS 삽입 |
| `frontend/detail.html` | Phase 2 코인 상세 | Modify: navbar 축소, 사이드바 HTML/CSS/JS 삽입, Bootstrap JS 번들 추가 |

생성되는 파일 없음. 백엔드 변경 없음.

---

## Task 1: index.html — Phase 1 섹션에 앵커 ID 부여

**Why first:** 이후 태스크의 사이드바 링크(`href="/#summary"` 등)와 IntersectionObserver 대상이 되는 DOM 앵커. 먼저 심어두면 독립적으로 커밋 가능하며, 사이드바가 없어도 페이지는 정상 동작한다.

**Files:**
- Modify: `frontend/index.html:143,209,269,295`

**Section → ID 매핑:**
| ID | 위치 | 내용 |
|----|------|------|
| `summary` | line 143 `<div class="row g-3 mb-4">` (요약 카드 5개) | 개요 |
| `returns` | line 215 기간별 수익률 래퍼 (신규 `<div>` 추가) | 수익률 분석 |
| `risk` | line 219 리스크 지표 래퍼 (신규 `<div>` 추가) | 리스크 지표 |
| `holdings` | line 269 `<div class="section-card bg-white mb-4">` (보유현황 테이블) | 보유현황 |
| `allocation` | line 295 `<div class="row g-3 mb-4">` (자산 배분 row) | 자산배분 |

- [ ] **Step 1: `summary` id 추가 (line 143)**

`frontend/index.html` 142~143행 찾기:
```html
    <!-- ① 요약 카드 5개 -->
    <div class="row g-3 mb-4">
```
→ 변경:
```html
    <!-- ① 요약 카드 5개 -->
    <div id="summary" class="row g-3 mb-4">
```

- [ ] **Step 2: `returns`/`risk` 래퍼 삽입 (line 213~246)**

현재 구조(line 211~247):
```html
        <div class="col-12 col-lg-5">
            <div class="section-card bg-white p-4 h-100">
                <div class="section-title">수익률 분석</div>
                <!-- 기간별 수익률 -->
                <div class="d-flex flex-wrap gap-2 mb-4" id="period-returns-row">
                    <span class="text-muted" style="font-size:.8rem;">데이터 로딩 중...</span>
                </div>
                <!-- 리스크 지표 -->
                <div class="section-title">리스크 지표</div>
                <div class="row g-2">
                    ... (4개 지표 col)
                </div>
            </div>
        </div>
```

두 개의 `<div>` 래퍼(`id="returns"`, `id="risk"`)로 감싸기:
```html
        <div class="col-12 col-lg-5">
            <div class="section-card bg-white p-4 h-100">
                <div id="returns">
                    <div class="section-title">수익률 분석</div>
                    <!-- 기간별 수익률 -->
                    <div class="d-flex flex-wrap gap-2 mb-4" id="period-returns-row">
                        <span class="text-muted" style="font-size:.8rem;">데이터 로딩 중...</span>
                    </div>
                </div>
                <div id="risk">
                    <div class="section-title">리스크 지표</div>
                    <div class="row g-2">
                        ... (기존 4개 지표 col 그대로)
                    </div>
                </div>
            </div>
        </div>
```

내부 지표 col 블록(MDD/변동성/샤프/HHI)은 **수정하지 않는다**. 단지 래퍼 `<div>` 두 개를 감싸고 들여쓰기만 재조정.

- [ ] **Step 3: `holdings` id 추가 (line 269)**

```html
    <!-- ③ 보유 현황 테이블 -->
    <div class="section-card bg-white mb-4">
```
→
```html
    <!-- ③ 보유 현황 테이블 -->
    <div id="holdings" class="section-card bg-white mb-4">
```

- [ ] **Step 4: `allocation` id 추가 (line 295)**

```html
    <!-- ④ 자산 배분 -->
    <div class="row g-3 mb-4">
```
→
```html
    <!-- ④ 자산 배분 -->
    <div id="allocation" class="row g-3 mb-4">
```

- [ ] **Step 5: 수동 검증 — 페이지 로드 무회귀**

1. `./manage_server.sh start` 실행(이미 떠 있다면 스킵).
2. 브라우저로 `http://localhost:8000`에 접속하고 로그인.
3. 대시보드가 예전과 동일하게 렌더되는지 시각 확인(요약 카드 5개, 수익률/리스크, 보유현황 테이블, 자산배분, Top5).
4. 브라우저 DevTools Console에서 JavaScript 에러가 없는지 확인.
5. DevTools Console에 아래 5개 명령을 입력하여 모두 `true`가 나오는지 확인:
   ```javascript
   !!document.getElementById('summary')
   !!document.getElementById('returns')
   !!document.getElementById('risk')
   !!document.getElementById('holdings')
   !!document.getElementById('allocation')
   ```
6. 주소창에 `http://localhost:8000/#risk`를 직접 입력해 리스크 지표 영역으로 스크롤되는지 확인.

- [ ] **Step 6: Commit**

```bash
git add frontend/index.html
git commit -m "feat(frontend): add section anchor ids for sidebar navigation

Phase 1 대시보드의 5개 섹션(summary/returns/risk/holdings/allocation)에
앵커 id를 부여하여 사이드바 스크롤스파이의 기반을 마련한다.
내부 구조는 그대로 두고 wrapper div 2개(returns/risk)만 추가."
```

---

## Task 2: index.html — 사이드바 CSS 추가

**Why before HTML:** CSS가 먼저 있으면 Task 3에서 HTML을 삽입하는 즉시 올바른 레이아웃으로 렌더된다(시각 회귀를 중간 단계에서 최소화).

**Files:**
- Modify: `frontend/index.html:10-105` (기존 `<style>` 블록 끝에 추가)

- [ ] **Step 1: 기존 `<style>` 블록 끝(line 104 `#skeleton-overlay` 다음) 앞에 사이드바 CSS 삽입**

`frontend/index.html` line 100~105 찾기:
```html
        .skeleton-text { height: 14px; margin-bottom: 6px; }
        .skeleton-h2   { height: 28px; }

        /* Loading overlay */
        #skeleton-overlay { position: fixed; inset: 0; background: var(--bg-main); z-index: 10; }
    </style>
```
→ `</style>` 바로 앞에 다음 블록 추가:
```html
        .skeleton-text { height: 14px; margin-bottom: 6px; }
        .skeleton-h2   { height: 28px; }

        /* Loading overlay */
        #skeleton-overlay { position: fixed; inset: 0; background: var(--bg-main); z-index: 10; }

        /* === Sidebar navigation === */
        html { scroll-behavior: smooth; }
        @media (min-width: 992px) {
            #sidebar {
                position: fixed; top: 0; left: 0;
                width: 240px; height: 100vh;
                border-right: 1px solid #e2e8f0;
                background: #fff;
                display: flex; flex-direction: column;
                z-index: 20;
            }
            body.has-sidebar > nav.navbar,
            body.has-sidebar > #main-content,
            body.has-sidebar > #skeleton-overlay,
            body.has-sidebar > #error-banner { margin-left: 240px; }
        }
        .sidebar-link {
            display: flex; align-items: center; gap: .6rem;
            padding: .55rem 1rem;
            color: #475569; text-decoration: none;
            font-size: .88rem;
            border-left: 3px solid transparent;
        }
        .sidebar-link:hover:not(.disabled) { background: #f8fafc; color: #0f172a; }
        .sidebar-link.active {
            background: #eff6ff; color: #1d4ed8;
            border-left-color: #1d4ed8; font-weight: 600;
        }
        .sidebar-link.disabled { color: #cbd5e1; cursor: not-allowed; }
        .sidebar-group-label {
            font-size: .7rem; font-weight: 700; color: #94a3b8;
            text-transform: uppercase; letter-spacing: .08em;
            padding: 1rem 1rem .4rem;
        }
        .sidebar-footer {
            padding: 1rem; border-top: 1px solid #e2e8f0;
            margin-top: auto;
        }
        .sidebar-link .badge { margin-left: auto; }
    </style>
```

- [ ] **Step 2: 수동 검증 — 스타일 파싱 무회귀**

1. 브라우저로 `http://localhost:8000` 새로고침.
2. DevTools Console에서 에러 없음 확인.
3. DevTools Elements 패널에서 아무 요소에 `sidebar-link` 클래스를 임시로 추가해보고 스타일이 적용되는지 확인(테스트 후 원복). 또는 Console에서:
   ```javascript
   const s = document.styleSheets;
   [...s].flatMap(x => { try { return [...x.cssRules] } catch { return [] } })
     .filter(r => r.selectorText && r.selectorText.includes('sidebar')).length
   ```
   결과가 10 이상이면 규칙이 제대로 파싱된 것.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "feat(frontend): add sidebar navigation CSS

사이드바 네비게이션을 위한 CSS 규칙을 index.html에 추가한다.
.offcanvas-lg 반응형 동작에 맞춰 데스크톱(≥992px)은 고정 사이드바,
그 이하에서는 offcanvas 기본값을 사용한다. 아직 HTML은 삽입하지 않았다."
```

---

## Task 3: index.html — 사이드바 HTML 삽입 + navbar 축소

**Files:**
- Modify: `frontend/index.html:107-119` (body 및 navbar 영역)

- [ ] **Step 1: `<body>` 태그에 `has-sidebar` 클래스 추가**

```html
<body>
```
→
```html
<body class="has-sidebar">
```

- [ ] **Step 2: 기존 navbar(line 109~119) 교체**

교체 전(line 109~119):
```html
<!-- Navbar -->
<nav class="navbar navbar-light bg-white border-bottom px-3 py-2">
    <div class="d-flex align-items-center gap-2">
        <i class="bi bi-bar-chart-line-fill fs-4 text-primary"></i>
        <span class="fw-bold fs-5">My Portfolio</span>
    </div>
    <div class="d-flex align-items-center gap-2">
        <span id="last-synced" class="text-muted" style="font-size:.78rem;"></span>
        <button onclick="logout()" class="btn btn-sm btn-outline-secondary">로그아웃</button>
    </div>
</nav>
```

교체 후(사이드바 `<aside>` + 축소된 navbar):
```html
<!-- Sidebar navigation -->
<aside id="sidebar" class="offcanvas-lg offcanvas-start" tabindex="-1" aria-labelledby="sidebar-label">
    <div class="offcanvas-header border-bottom">
        <span id="sidebar-label" class="fw-bold">
            <i class="bi bi-bar-chart-line-fill text-primary"></i> My Portfolio
        </span>
        <button type="button" class="btn-close d-lg-none"
                data-bs-dismiss="offcanvas" data-bs-target="#sidebar" aria-label="Close"></button>
    </div>
    <nav class="offcanvas-body d-flex flex-column p-0">
        <div class="sidebar-group-label">대시보드</div>
        <a href="/#summary"    class="sidebar-link" data-nav="summary">개요</a>
        <a href="/#holdings"   class="sidebar-link" data-nav="holdings">보유현황</a>
        <a href="/#returns"    class="sidebar-link" data-nav="returns">수익률 분석</a>
        <a href="/#allocation" class="sidebar-link" data-nav="allocation">자산배분</a>
        <a href="/#risk"       class="sidebar-link" data-nav="risk">리스크 지표</a>

        <div class="sidebar-group-label">분석</div>
        <span class="sidebar-link disabled">뉴스 리포트 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">시장 상황판 <span class="badge text-bg-light">준비중</span></span>

        <div class="sidebar-group-label">도구</div>
        <span class="sidebar-link disabled">가격 알림 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">리밸런싱 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">트레이드 저널 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">수익 실현 계산기 <span class="badge text-bg-light">준비중</span></span>

        <div class="sidebar-group-label">기타</div>
        <span class="sidebar-link disabled">설정 <span class="badge text-bg-light">준비중</span></span>

        <div class="sidebar-footer">
            <span id="last-synced" class="text-muted small d-block mb-2"></span>
            <button onclick="logout()" class="btn btn-sm btn-outline-secondary w-100">
                <i class="bi bi-box-arrow-right"></i> 로그아웃
            </button>
        </div>
    </nav>
</aside>

<!-- Mobile navbar (only visible <992px) -->
<nav class="navbar navbar-light bg-white border-bottom px-3 py-2 d-lg-none">
    <button class="btn btn-sm" type="button"
            data-bs-toggle="offcanvas" data-bs-target="#sidebar" aria-controls="sidebar">
        <i class="bi bi-list fs-4"></i>
    </button>
    <span class="fw-bold">My Portfolio</span>
    <span style="width:32px"></span>
</nav>
```

**중요:** 기존 navbar 안에 있던 `<span id="last-synced">`와 `<button onclick="logout()">`은 **완전히 제거**하여 사이드바 footer에만 존재하게 만든다. `id="last-synced"`가 문서에 두 번 나오지 않도록 주의(기존 JS `document.getElementById('last-synced')`가 사이드바 footer의 span을 찾게 됨).

- [ ] **Step 3: 수동 검증 — 데스크톱 레이아웃**

1. 브라우저 창을 1200px 이상 너비로 확장.
2. `http://localhost:8000` 새로고침.
3. 확인 사항:
   - [ ] 좌측에 240px 폭의 사이드바가 고정 표시된다.
   - [ ] 상단 모바일 navbar(`d-lg-none`)는 표시되지 않는다.
   - [ ] 본문(요약 카드, 테이블 등)이 사이드바에 가려지지 않고 오른쪽으로 밀려 있다.
   - [ ] 사이드바 항목 "개요/보유현황/수익률 분석/자산배분/리스크 지표" 클릭 시 해당 섹션으로 부드럽게 스크롤된다.
   - [ ] "준비중" 항목에 커서를 올리면 `not-allowed`, 클릭해도 이동하지 않는다.
   - [ ] 사이드바 하단의 "로그아웃" 버튼이 동작한다(클릭 시 `/login.html`로 이동 후 다시 로그인).
   - [ ] `#last-synced` 문구가 사이드바 footer에 렌더된다(데이터 로딩 후 "마지막 동기화: …" 형태).

- [ ] **Step 4: 수동 검증 — 모바일 레이아웃**

1. DevTools → Device Toolbar → 375px (iPhone SE 등).
2. 새로고침.
3. 확인 사항:
   - [ ] 사이드바가 숨겨지고 상단에 햄버거 버튼이 있는 navbar가 보인다.
   - [ ] 햄버거 탭 시 좌측에서 offcanvas가 슬라이드 인된다.
   - [ ] offcanvas 바깥 탭 또는 우상단 X 버튼으로 닫힌다.
   - [ ] 메뉴 항목 탭은 이동하지만 offcanvas가 자동 닫히지는 **않는다**(Task 4에서 해결 예정). 이 단계에서 자동 닫힘이 안 돼도 정상.

- [ ] **Step 5: Commit**

```bash
git add frontend/index.html
git commit -m "feat(frontend): insert sidebar navigation and reduce navbar

Phase 1 대시보드에 공통 사이드바(.offcanvas-lg)를 삽입하고
기존 navbar를 모바일 전용 햄버거 + 타이틀로 축소한다.
로그아웃과 last-synced 표시는 사이드바 footer로 이동.
활성 링크 자동 하이라이트와 모바일 자동 닫힘은 다음 태스크에서 처리."
```

---

## Task 4: index.html — 사이드바 JS (스크롤스파이 + offcanvas 자동 닫힘)

**Files:**
- Modify: `frontend/index.html` 기존 `<script>` 블록 끝(마지막 `</script>` 직전)

**Context:** 이 파일은 `<script>` 블록이 line ~344 부근에 있고 내부에 `loadPortfolio()`, `loadAnalytics()` 등 기존 로직이 있다. 사이드바 JS는 파일 최하단 `</script>` 직전에 **새 IIFE 블록**으로 추가하여 기존 코드와 충돌하지 않게 한다.

- [ ] **Step 1: 기존 `<script>` 블록 끝에 사이드바 스크립트 추가**

`frontend/index.html`의 마지막 `</script>` 태그를 찾는다(파일 끝 근처). 그 바로 위에 다음 블록을 삽입:

```javascript
// ── Sidebar scroll-spy + offcanvas auto-close ─────────────────────────────────
(function initSidebar() {
    const sectionIds = ['summary', 'returns', 'risk', 'holdings', 'allocation'];
    const visible = new Set();

    const observer = new IntersectionObserver((entries) => {
        entries.forEach(e => {
            if (e.isIntersecting) visible.add(e.target.id);
            else visible.delete(e.target.id);
        });
        // 문서 순서상 마지막으로 교차 중인 섹션을 활성으로 선택
        // (리스크 지표가 수익률 분석 카드 안에 중첩되어 있어 이 처리가 필요하다)
        const active = sectionIds.filter(id => visible.has(id)).pop();
        if (!active) return;
        document.querySelectorAll('#sidebar .sidebar-link').forEach(el => el.classList.remove('active'));
        const link = document.querySelector(`#sidebar .sidebar-link[data-nav="${active}"]`);
        if (link) link.classList.add('active');
    }, { rootMargin: '-20% 0px -70% 0px' });

    sectionIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) observer.observe(el);
    });

    // 모바일에서 메뉴 탭 시 offcanvas 자동 닫힘
    const sidebarEl = document.getElementById('sidebar');
    document.querySelectorAll('#sidebar .sidebar-link:not(.disabled)').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth < 992 && sidebarEl) {
                const inst = bootstrap.Offcanvas.getInstance(sidebarEl)
                           || bootstrap.Offcanvas.getOrCreateInstance(sidebarEl);
                inst.hide();
            }
        });
    });
})();
```

**Note:** `bootstrap.Offcanvas`는 index.html이 이미 line 342에서 `bootstrap.bundle.min.js`를 로드하므로 사용 가능하다.

- [ ] **Step 2: 수동 검증 — 스크롤스파이 (데스크톱)**

1. 창 너비 ≥1200px, `http://localhost:8000` 새로고침.
2. 처음 로드 시 "개요" 링크가 활성 상태(왼쪽 파란 보더 + 연한 파란 배경).
3. 천천히 아래로 스크롤하면서 다음 순서로 활성 링크가 바뀌는지 확인:
   - 개요 → 수익률 분석 → 리스크 지표 → 보유현황 → 자산배분
4. 사이드바 링크를 클릭하면 해당 섹션으로 이동하며 잠시 후 활성 상태도 링크에 맞게 갱신된다.
5. Console에 에러가 없어야 한다.

**중첩 섹션 특수 케이스:** "수익률 분석"과 "리스크 지표"는 같은 카드 안에 있으므로, 사용자가 수익률 분석 영역에 있을 때는 `returns`만, 리스크 영역으로 스크롤하면 `risk`가 활성이어야 한다. "문서 순서상 마지막" 로직이 이 동작을 보장한다. 만약 리스크 영역인데도 "수익률 분석"이 활성인 채로 남아 있으면 `rootMargin` 값을 조정하거나 스펙 자체를 재검토할 것.

- [ ] **Step 3: 수동 검증 — offcanvas 자동 닫힘 (모바일)**

1. DevTools Device Toolbar → 375px.
2. 새로고침 → 햄버거 탭 → offcanvas 열림 → "보유현황" 탭.
3. 확인 사항:
   - [ ] offcanvas가 자동으로 닫힌다.
   - [ ] 보유현황 테이블 섹션으로 스크롤 이동한다.
4. 햄버거 탭 → "뉴스 리포트"(준비중) 탭 → 닫히지 않고 아무 일도 일어나지 않는다(disabled 링크는 리스너 대상 제외).

- [ ] **Step 4: Commit**

```bash
git add frontend/index.html
git commit -m "feat(frontend): add sidebar scroll-spy and offcanvas auto-close

IntersectionObserver로 Phase 1 섹션의 현재 뷰를 추적해 사이드바
활성 링크를 자동 하이라이트한다. 리스크 지표가 수익률 분석 카드 안에
중첩되어 있어 '문서 순서상 마지막으로 교차한 섹션'을 선택하는 로직
사용. 모바일에서는 메뉴 탭 시 offcanvas가 자동으로 닫힌다."
```

---

## Task 5: detail.html — Bootstrap JS 번들 추가

**Why:** 현재 detail.html은 Bootstrap CSS만 로드하고 JS 번들(`bootstrap.bundle.min.js`)은 누락되어 있다. Task 7에서 사이드바 offcanvas를 사용하려면 `data-bs-toggle="offcanvas"`와 `bootstrap.Offcanvas` API가 필요하다. 이 태스크는 **새 의존성 추가가 아니라 index.html에 이미 있는 것과 동일한 의존성을 detail.html에도 맞춰 넣는 것**이다.

**Files:**
- Modify: `frontend/detail.html:10`

- [ ] **Step 1: `<head>`의 Chart.js `<script>` 위에 Bootstrap JS 번들 추가**

현재 line 10:
```html
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
```
→ 바로 위에 한 줄 삽입(defer 없이, `</body>` 직전이 아닌 `<head>`에 두어 기존 Chart.js 로드와 동일 위치 유지):
```html
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.3/dist/chart.umd.min.js"></script>
```

- [ ] **Step 2: 수동 검증 — detail 페이지 무회귀**

1. `http://localhost:8000`에서 보유현황 테이블의 코인 행(예: BTC)을 클릭해 detail.html로 이동.
2. 페이지가 정상 로드되고 Console 에러가 없는지 확인.
3. Console에서 `typeof bootstrap.Offcanvas` 입력 → `'function'` 이 나오면 성공.

- [ ] **Step 3: Commit**

```bash
git add frontend/detail.html
git commit -m "chore(frontend): add Bootstrap JS bundle to detail.html

기존 detail.html은 Bootstrap CSS만 로드하고 JS 번들은 누락되어
offcanvas 등 JS 기반 컴포넌트를 사용할 수 없었다. index.html과 동일한
bootstrap.bundle.min.js를 추가하여 이후 사이드바 offcanvas 도입을 준비."
```

---

## Task 6: detail.html — 사이드바 CSS 추가

**Files:**
- Modify: `frontend/detail.html:11-58` 내 `<style>` 블록 끝

- [ ] **Step 1: 기존 `<style>` 블록 끝(line 58 `</style>` 직전)에 Task 2와 동일한 CSS 블록 추가**

`frontend/detail.html` line 56~58 찾기:
```html
        #loading-overlay {
            position: fixed; inset: 0; background: var(--bg-main); z-index: 100;
            display: flex; align-items: center; justify-content: center;
        }
    </style>
```
→ `</style>` 앞에 다음을 삽입:
```html
        #loading-overlay {
            position: fixed; inset: 0; background: var(--bg-main); z-index: 100;
            display: flex; align-items: center; justify-content: center;
        }

        /* === Sidebar navigation === */
        html { scroll-behavior: smooth; }
        @media (min-width: 992px) {
            #sidebar {
                position: fixed; top: 0; left: 0;
                width: 240px; height: 100vh;
                border-right: 1px solid #e2e8f0;
                background: #fff;
                display: flex; flex-direction: column;
                z-index: 20;
            }
            body.has-sidebar > nav.navbar,
            body.has-sidebar > #main-content,
            body.has-sidebar > #loading-overlay { margin-left: 240px; }
        }
        .sidebar-link {
            display: flex; align-items: center; gap: .6rem;
            padding: .55rem 1rem;
            color: #475569; text-decoration: none;
            font-size: .88rem;
            border-left: 3px solid transparent;
        }
        .sidebar-link:hover:not(.disabled) { background: #f8fafc; color: #0f172a; }
        .sidebar-link.active {
            background: #eff6ff; color: #1d4ed8;
            border-left-color: #1d4ed8; font-weight: 600;
        }
        .sidebar-link.disabled { color: #cbd5e1; cursor: not-allowed; }
        .sidebar-group-label {
            font-size: .7rem; font-weight: 700; color: #94a3b8;
            text-transform: uppercase; letter-spacing: .08em;
            padding: 1rem 1rem .4rem;
        }
        .sidebar-footer {
            padding: 1rem; border-top: 1px solid #e2e8f0;
            margin-top: auto;
        }
        .sidebar-link .badge { margin-left: auto; }
    </style>
```

**주의:** 이 CSS 블록은 Task 2의 것과 **거의 동일**하지만 `margin-left: 240px` 규칙의 대상이 다르다. detail.html은 `#skeleton-overlay`/`#error-banner` 대신 `#loading-overlay`를 가진다(line 63). 위 코드 블록은 그 차이를 이미 반영했다.

- [ ] **Step 2: 수동 검증 — CSS 파싱 무회귀**

1. detail.html 페이지 새로고침.
2. Console 에러 없음 확인.

- [ ] **Step 3: Commit**

```bash
git add frontend/detail.html
git commit -m "feat(frontend): add sidebar navigation CSS to detail.html

index.html과 동일한 사이드바 CSS 규칙을 detail.html에 추가한다.
margin-left 대상만 detail 고유의 #loading-overlay에 맞춰 조정."
```

---

## Task 7: detail.html — 사이드바 HTML 삽입 + navbar 축소

**Files:**
- Modify: `frontend/detail.html:60-79`

- [ ] **Step 1: `<body>`에 `has-sidebar` 추가**

```html
<body>
```
→
```html
<body class="has-sidebar">
```

- [ ] **Step 2: 기존 navbar(line 70~79)를 사이드바 + 축소 navbar로 교체**

교체 전:
```html
<!-- Navbar -->
<nav class="navbar navbar-light bg-white border-bottom px-3 py-2">
    <div class="d-flex align-items-center gap-2">
        <a href="/" class="btn btn-sm btn-outline-secondary d-flex align-items-center gap-1">
            <i class="bi bi-arrow-left"></i> 대시보드
        </a>
        <span id="nav-title" class="fw-semibold fs-6 ms-1">—</span>
    </div>
    <button onclick="logout()" class="btn btn-sm btn-outline-secondary">로그아웃</button>
</nav>
```

교체 후:
```html
<!-- Sidebar navigation -->
<aside id="sidebar" class="offcanvas-lg offcanvas-start" tabindex="-1" aria-labelledby="sidebar-label">
    <div class="offcanvas-header border-bottom">
        <span id="sidebar-label" class="fw-bold">
            <i class="bi bi-bar-chart-line-fill text-primary"></i> My Portfolio
        </span>
        <button type="button" class="btn-close d-lg-none"
                data-bs-dismiss="offcanvas" data-bs-target="#sidebar" aria-label="Close"></button>
    </div>
    <nav class="offcanvas-body d-flex flex-column p-0">
        <div class="sidebar-group-label">대시보드</div>
        <a href="/#summary"    class="sidebar-link" data-nav="summary">개요</a>
        <a href="/#holdings"   class="sidebar-link" data-nav="holdings">보유현황</a>
        <a href="/#returns"    class="sidebar-link" data-nav="returns">수익률 분석</a>
        <a href="/#allocation" class="sidebar-link" data-nav="allocation">자산배분</a>
        <a href="/#risk"       class="sidebar-link" data-nav="risk">리스크 지표</a>

        <div class="sidebar-group-label">분석</div>
        <span class="sidebar-link disabled">뉴스 리포트 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">시장 상황판 <span class="badge text-bg-light">준비중</span></span>

        <div class="sidebar-group-label">도구</div>
        <span class="sidebar-link disabled">가격 알림 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">리밸런싱 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">트레이드 저널 <span class="badge text-bg-light">준비중</span></span>
        <span class="sidebar-link disabled">수익 실현 계산기 <span class="badge text-bg-light">준비중</span></span>

        <div class="sidebar-group-label">기타</div>
        <span class="sidebar-link disabled">설정 <span class="badge text-bg-light">준비중</span></span>

        <div class="sidebar-footer">
            <button onclick="logout()" class="btn btn-sm btn-outline-secondary w-100">
                <i class="bi bi-box-arrow-right"></i> 로그아웃
            </button>
        </div>
    </nav>
</aside>

<!-- Mobile navbar (only visible <992px) -->
<nav class="navbar navbar-light bg-white border-bottom px-3 py-2 d-lg-none">
    <button class="btn btn-sm" type="button"
            data-bs-toggle="offcanvas" data-bs-target="#sidebar" aria-controls="sidebar">
        <i class="bi bi-list fs-4"></i>
    </button>
    <span id="nav-title" class="fw-semibold fs-6">—</span>
    <span style="width:32px"></span>
</nav>
```

**중요:**
- 기존 navbar의 "← 대시보드" 버튼은 삭제한다(사이드바의 "개요" 링크가 역할 수행). 로그아웃 버튼도 navbar에서 제거하고 사이드바 footer에만 둔다.
- `id="nav-title"`은 반드시 유지한다. detail.html의 기존 JS가 `document.getElementById('nav-title').textContent = ...`로 코인 이름을 넣는다(`renderCoinHeader` 등). 모바일 navbar에 그대로 배치.
- detail.html에는 `#last-synced`가 원래 없으므로 사이드바 footer에도 넣지 않는다(index.html과 사이드바 footer만 약간 다름).

- [ ] **Step 3: 수동 검증 — 데스크톱**

1. 창 ≥1200px로 확대.
2. 보유 코인 행(BTC 등) 클릭 → detail.html 진입.
3. 확인:
   - [ ] 좌측 240px 사이드바가 보인다.
   - [ ] 상단 모바일 navbar는 보이지 않는다(`d-lg-none`).
   - [ ] 코인 헤더/차트가 사이드바 오른쪽 영역에 정상 렌더된다.
   - [ ] 사이드바의 "개요" 링크 클릭 → index.html로 이동 + `#summary`로 스크롤.
   - [ ] 사이드바의 "보유현황" 링크 클릭 → index.html로 이동 + `#holdings`로 스크롤.
   - [ ] 사이드바의 "로그아웃" 버튼이 동작한다.

- [ ] **Step 4: 수동 검증 — 모바일**

1. DevTools → 375px.
2. 새로고침.
3. 확인:
   - [ ] 상단 navbar에 햄버거 + 코인 이름(`#nav-title`)이 보인다.
   - [ ] 햄버거 탭 → offcanvas 슬라이드 인.
   - [ ] X 버튼이나 외부 탭으로 닫힘.
   - [ ] 메뉴 탭 시 index.html로 이동(자동 닫힘은 Task 8에서 처리).

- [ ] **Step 5: Commit**

```bash
git add frontend/detail.html
git commit -m "feat(frontend): insert sidebar navigation into detail.html

Phase 2 코인 상세 페이지에 공통 사이드바를 삽입하고 기존 navbar의
'← 대시보드'/로그아웃을 사이드바로 이전한다. nav-title은 모바일
navbar에 그대로 유지하여 기존 JS(renderCoinHeader 등)와 호환."
```

---

## Task 8: detail.html — offcanvas 자동 닫힘 스크립트

**Files:**
- Modify: `frontend/detail.html` 기존 `<script>` 블록 끝

- [ ] **Step 1: 기존 `<script>` 블록 끝(마지막 `</script>` 직전)에 삽입**

`frontend/detail.html`의 마지막 `</script>` 태그를 찾아 바로 앞에 다음 블록 추가:

```javascript
// ── Sidebar offcanvas auto-close (detail page, no scroll-spy) ─────────────────
(function initSidebarDetail() {
    const sidebarEl = document.getElementById('sidebar');
    document.querySelectorAll('#sidebar .sidebar-link:not(.disabled)').forEach(link => {
        link.addEventListener('click', () => {
            if (window.innerWidth < 992 && sidebarEl) {
                const inst = bootstrap.Offcanvas.getInstance(sidebarEl)
                           || bootstrap.Offcanvas.getOrCreateInstance(sidebarEl);
                inst.hide();
            }
        });
    });
})();
```

**Note:** detail.html에는 Phase 1 섹션이 없으므로 IntersectionObserver 로직은 넣지 않는다. 사이드바의 링크는 전부 `/#xxx`(index.html로 이동)이며 현재 페이지에 대응되는 활성 상태가 없으므로 초기 활성 하이라이트도 없다.

- [ ] **Step 2: 수동 검증 — 모바일 자동 닫힘**

1. DevTools → 375px.
2. detail.html 로드.
3. 햄버거 탭 → 메뉴 열림 → "개요" 탭.
4. 확인:
   - [ ] offcanvas가 자동으로 닫힌다.
   - [ ] index.html의 summary 섹션으로 이동한다.
5. 다시 detail로 진입 후 "뉴스 리포트"(준비중) 탭 → 아무 일도 일어나지 않음(disabled).

- [ ] **Step 3: Commit**

```bash
git add frontend/detail.html
git commit -m "feat(frontend): add sidebar offcanvas auto-close on detail.html

detail.html은 Phase 1 섹션이 없으므로 스크롤스파이는 생략하고
모바일 메뉴 탭 시 offcanvas 자동 닫힘 리스너만 등록한다."
```

---

## Task 9: End-to-end 수동 검증 + 스펙 체크리스트 확인

**Why:** 개별 태스크 검증을 통과해도 조합 회귀가 있을 수 있다. 스펙(`docs/superpowers/specs/2026-04-11-sidebar-navigation-design.md`) 섹션 8의 테스트 계획을 한 번에 돌리고 체크박스를 모두 메운다.

- [ ] **Step 1: 서버 재시작**

```bash
./manage_server.sh stop
./manage_server.sh start
```

- [ ] **Step 2: 데스크톱 ≥992px 시나리오 (스펙 8.1)**

Chrome 창 너비 1400px 이상으로 설정 후 `http://localhost:8000`에 로그인 상태로 접속.

- [ ] 사이드바가 좌측 240px 고정 표시.
- [ ] navbar가 숨겨진다(`d-lg-none`).
- [ ] "개요/보유현황/수익률/자산배분/리스크" 클릭 시 부드럽게 스크롤.
- [ ] 스크롤 시 뷰포트에 들어온 섹션이 자동 하이라이트(summary → returns → risk → holdings → allocation 순).
- [ ] 준비중 항목 클릭 불가(`not-allowed`).
- [ ] 로그아웃 버튼 정상 동작.
- [ ] `detail.html`에서도 사이드바 동일 표시, "개요" 링크 → `/#summary` 이동.

- [ ] **Step 3: 모바일 <992px 시나리오 (스펙 8.2)**

DevTools Device Toolbar iPhone SE(375px).

- [ ] 사이드바 숨김, 상단에 햄버거 navbar 표시.
- [ ] 햄버거 탭 → offcanvas 슬라이드 인.
- [ ] 외부 탭/닫기 버튼으로 닫힘.
- [ ] 메뉴 항목 탭 시 offcanvas 자동 닫힘 + 해당 섹션 이동.

- [ ] **Step 4: detail.html 시나리오 (스펙 8.3)**

- [ ] 사이드바 렌더, 활성 항목 없음.
- [ ] "개요" 탭 시 `/#summary`로 이동(index.html 로드).
- [ ] 코인 헤더 `#nav-title`(모바일 navbar)이 여전히 코인 이름 표시.

- [ ] **Step 5: 회귀 체크 — 기존 기능 무변경**

- [ ] Phase 1 요약 카드 5개 값 정상 로드.
- [ ] 수익률 분석 기간별 pill 정상 표시.
- [ ] 리스크 지표 4개 값 정상 표시.
- [ ] 보유현황 테이블 행 클릭 → detail 이동.
- [ ] 누적 수익률 차트, 자산배분 도넛/트리맵 렌더.
- [ ] Top 5 / 상관관계 매트릭스 정상 표시.
- [ ] `./manage_server.sh status` 로 백엔드 동기화 정상 확인.

- [ ] **Step 6: Console/Network 클린 체크**

- [ ] index.html, detail.html 모두 Console에 경고/에러가 없다(기존 예외 외).
- [ ] Network 탭에서 새 리소스는 `bootstrap.bundle.min.js`(detail.html) 추가 1건 외에 변동 없음.

- [ ] **Step 7: 최종 상태 기록 + 머지 준비**

`git log --oneline -10` 으로 다음 8개 커밋이 쌓였는지 확인:
1. feat(frontend): add section anchor ids for sidebar navigation
2. feat(frontend): add sidebar navigation CSS
3. feat(frontend): insert sidebar navigation and reduce navbar
4. feat(frontend): add sidebar scroll-spy and offcanvas auto-close
5. chore(frontend): add Bootstrap JS bundle to detail.html
6. feat(frontend): add sidebar navigation CSS to detail.html
7. feat(frontend): insert sidebar navigation into detail.html
8. feat(frontend): add sidebar offcanvas auto-close on detail.html

위 모든 체크가 통과하면 이 기능은 완료. 이후 superpowers:finishing-a-development-branch 스킬로 PR/머지 경로를 결정한다.

---

## Self-Review Notes

**Spec coverage** (spec `docs/superpowers/specs/2026-04-11-sidebar-navigation-design.md` 기준):
- Spec §3 레이아웃(데스크톱 240px / 모바일 offcanvas): Task 2-3, 6-7 ✓
- Spec §4 항목 구성(대시보드 5 / 분석 2 / 도구 4 / 기타 1): Task 3, 7 ✓
- Spec §5.1 공통 마크업: Task 3, 7 ✓
- Spec §5.2 CSS: Task 2, 6 ✓
- Spec §5.3 navbar 축소: Task 3, 7 ✓
- Spec §6.1 스크롤스파이: Task 4 ✓ (단, 중첩 섹션 대응을 위해 "pop() 후 활성화" 로직 추가)
- Spec §6.2 offcanvas 자동 닫힘: Task 4, 8 ✓
- Spec §6.3 detail.html은 scroll-spy 제외: Task 8 ✓
- Spec §6.4 CSS 스무스 스크롤: Task 2, 6 ✓
- Spec §7 영향 범위(`#last-synced` 중복 금지): Task 3 명시 ✓
- Spec §8 테스트 계획: Task 9로 통째 재수행 ✓

**Placeholder scan:** "TBD/TODO/implement later/fill in details" 없음. 모든 코드 블록 완전함. 에러 핸들링/검증은 필요한 지점에만 노출("getInstance 없을 시 getOrCreateInstance fallback", "innerWidth < 992 가드").

**Type/이름 일관성:**
- `id="sidebar"` / `#sidebar`: Task 3, 4, 7, 8 모두 동일
- `class="sidebar-link"` 대/소문자 일관: 모든 태스크 동일
- `data-nav="{id}"` ↔ `sectionIds`: Task 3 링크와 Task 4 observer의 섹션 id가 정확히 일치(summary/returns/risk/holdings/allocation)
- `sidebar-group-label`, `sidebar-footer`, `has-sidebar` 클래스명: CSS(Task 2,6)와 HTML(Task 3,7) 일치

**Scope:** 프론트엔드 2개 파일만. 백엔드/DB/라우터 건드리지 않음. YAGNI로 공통 `assets/` 분리는 미포함(spec §7에 명시).

---

**Plan complete and saved to `docs/superpowers/plans/2026-04-11-sidebar-navigation.md`. Two execution options:**

**1. Subagent-Driven (recommended)** - 태스크마다 fresh subagent를 띄우고 사이에 리뷰, 빠른 반복

**2. Inline Execution** - 이 세션에서 직접 태스크 실행, 체크포인트마다 확인

**Which approach?**
