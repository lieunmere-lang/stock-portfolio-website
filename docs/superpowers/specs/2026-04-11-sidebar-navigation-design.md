# 사이드바 네비게이션 설계안

- 작성일: 2026-04-11
- 범위: 프론트엔드 전용 (`frontend/index.html`, `frontend/detail.html`)
- 목표: 페이지·섹션 전환 수단이 없는 현재 구조에 공통 사이드바를 도입하여, Phase 1 섹션 간 이동과 향후 Phase 3~5 페이지 확장을 지원한다.

---

## 1. 배경

- Phase 1 대시보드(`index.html`)와 Phase 2 코인 상세(`detail.html`)가 구현되어 있다.
- 현재 페이지 간 이동 수단은 navbar의 로고/"← 대시보드" 버튼뿐이라 확장성이 낮다.
- 요구사항 문서(`docs/requirements/`)에 Phase 3(뉴스 리포트), Phase 4(가격 알림 / 리밸런싱 / 트레이드 저널 / 시장 상황판 등), Phase 5(키움 연동)가 예정되어 있어 페이지 수가 계속 늘어날 예정이다.
- 이 설계의 스코프는 "사이드바 도입"이며, Phase 1을 재설계하거나 프론트엔드 에셋 구조를 분리하는 작업은 포함하지 않는다.

---

## 2. 결정 사항 요약

| 항목 | 결정 |
|------|------|
| 사이드바 항목 구성 | 전 Phase를 미리 반영하되, 미구현 항목은 "준비중" 비활성으로 표시 |
| Phase 1 내부 섹션 이동 | **앵커 스크롤** (페이지 분리 없이 기존 `index.html` 그대로) |
| 반응형 동작 | 데스크톱(≥992px): 240px 고정 사이드바 / 모바일(<992px): Bootstrap offcanvas |
| 코인 상세 메뉴 항목 | 제외. 상세 페이지는 보유현황 테이블 행 클릭으로만 진입 |
| 로그아웃 위치 | 사이드바 하단으로 이동 (navbar에서 제거) |
| 그룹 구성 | 대시보드 / 분석 / 도구 / 기타 |

---

## 3. 레이아웃

```
데스크톱 (≥992px)                 모바일 (<992px)
┌─────────┬──────────────────┐    ┌──────────────────┐
│         │  navbar          │    │ ☰ navbar         │
│ sidebar ├──────────────────┤    ├──────────────────┤
│ 240px   │                  │    │                  │
│ 고정    │   main content   │    │   main content   │
│         │                  │    │                  │
│ [logout]│                  │    │                  │
└─────────┴──────────────────┘    └──────────────────┘
                                   ☰ 탭 → offcanvas 슬라이드 인
```

- **데스크톱**: `position: fixed; width: 240px;` 좌측 고정, 본문에 `margin-left: 240px` 적용.
- **모바일**: Bootstrap 5.2+의 `.offcanvas-lg` 반응형 offcanvas 사용. lg 브레이크포인트 미만에서만 오버레이로 전환되고, 이상에서는 일반 블록처럼 동작하여 별도 JS 분기가 불필요하다.
- navbar는 **축소**: 모바일 햄버거 버튼 + 페이지 타이틀만 유지. 기존 로고와 로그아웃은 사이드바로 이동.

---

## 4. 사이드바 항목

```
━━━ 대시보드 ━━━
  개요          → /#summary
  보유현황      → /#holdings
  수익률 분석   → /#returns
  자산배분      → /#allocation
  리스크 지표   → /#risk

━━━ 분석 ━━━
  뉴스 리포트   [준비중, Phase 3]
  시장 상황판   [준비중, Phase 4-5]

━━━ 도구 ━━━
  가격 알림          [준비중, Phase 4-1]
  리밸런싱           [준비중, Phase 4-3]
  트레이드 저널      [준비중, Phase 4-4]
  수익 실현 계산기   [준비중, Phase 4-2]

━━━ 기타 ━━━
  설정          [준비중]

  [footer]
  last-synced 텍스트
  🚪 로그아웃 버튼
```

- 활성 항목은 좌측 3px 보더 + 연한 파란 배경으로 하이라이트.
- 준비중 항목은 `<a>`가 아닌 `<span class="sidebar-link disabled">`로 렌더하여 클릭/링크 차단. 우측에 `badge` "준비중" 라벨 부착.

---

## 5. DOM / CSS 구조

### 5.1 공통 사이드바 마크업 (양 HTML에 동일 삽입)

```html
<aside id="sidebar" class="offcanvas-lg offcanvas-start" tabindex="-1">
  <div class="offcanvas-header">
    <span class="fw-bold">
      <i class="bi bi-bar-chart-line-fill text-primary"></i> My Portfolio
    </span>
    <button class="btn-close d-lg-none"
            data-bs-dismiss="offcanvas"
            data-bs-target="#sidebar"></button>
  </div>
  <nav class="offcanvas-body flex-column p-0">
    <div class="sidebar-group-label">대시보드</div>
    <a href="/#summary"    class="sidebar-link" data-nav="summary">개요</a>
    <a href="/#holdings"   class="sidebar-link" data-nav="holdings">보유현황</a>
    <a href="/#returns"    class="sidebar-link" data-nav="returns">수익률 분석</a>
    <a href="/#allocation" class="sidebar-link" data-nav="allocation">자산배분</a>
    <a href="/#risk"       class="sidebar-link" data-nav="risk">리스크 지표</a>

    <div class="sidebar-group-label">분석</div>
    <span class="sidebar-link disabled">뉴스 리포트 <span class="badge text-bg-light ms-auto">준비중</span></span>
    <span class="sidebar-link disabled">시장 상황판 <span class="badge text-bg-light ms-auto">준비중</span></span>

    <div class="sidebar-group-label">도구</div>
    <span class="sidebar-link disabled">가격 알림 <span class="badge text-bg-light ms-auto">준비중</span></span>
    <span class="sidebar-link disabled">리밸런싱 <span class="badge text-bg-light ms-auto">준비중</span></span>
    <span class="sidebar-link disabled">트레이드 저널 <span class="badge text-bg-light ms-auto">준비중</span></span>
    <span class="sidebar-link disabled">수익 실현 계산기 <span class="badge text-bg-light ms-auto">준비중</span></span>

    <div class="sidebar-group-label">기타</div>
    <span class="sidebar-link disabled">설정 <span class="badge text-bg-light ms-auto">준비중</span></span>

    <div class="sidebar-footer mt-auto">
      <span id="last-synced" class="text-muted small d-block mb-2"></span>
      <button onclick="logout()" class="btn btn-sm btn-outline-secondary w-100">
        <i class="bi bi-box-arrow-right"></i> 로그아웃
      </button>
    </div>
  </nav>
</aside>
```

### 5.2 공통 CSS (양 파일의 `<style>` 블록에 추가)

```css
html { scroll-behavior: smooth; }

@media (min-width: 992px) {
  #sidebar {
    position: fixed; top: 0; left: 0;
    width: 240px; height: 100vh;
    border-right: 1px solid #e2e8f0;
    background: #fff;
    display: flex; flex-direction: column;
  }
  body.has-sidebar > nav.navbar,
  body.has-sidebar > main,
  body.has-sidebar > #main-content,
  body.has-sidebar > #skeleton-overlay {
    margin-left: 240px;
  }
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
```

- `<body>`에 `class="has-sidebar"`를 추가하여 본문 여백 적용. `margin-left` 셀렉터는 기존 요소 구조(`#main-content`, `#skeleton-overlay`, `main`, `navbar`)에 맞춘다.

### 5.3 navbar 변경

- **`index.html`**: 기존 `<nav class="navbar">`의 로고/로그아웃 블록 제거. 대신 모바일용 햄버거 버튼 + 타이틀만 유지.
  ```html
  <nav class="navbar navbar-light bg-white border-bottom px-3 py-2 d-lg-none">
    <button class="btn btn-sm" data-bs-toggle="offcanvas" data-bs-target="#sidebar">
      <i class="bi bi-list fs-4"></i>
    </button>
    <span class="fw-bold">My Portfolio</span>
    <span style="width:32px"></span>
  </nav>
  ```
  - `d-lg-none`: 데스크톱에서는 navbar 자체를 숨기고 사이드바에 모든 기능 집약.
- **`detail.html`**: 기존 "← 대시보드" 버튼 제거(사이드바 "개요" 링크로 대체). navbar는 동일하게 모바일 전용 햄버거 + 타이틀(`#nav-title`) 유지.

---

## 6. JavaScript 동작

### 6.1 활성 링크 하이라이트 (index.html 전용)

IntersectionObserver로 현재 뷰포트에 보이는 섹션을 추적한다.

```javascript
const sections = ['summary', 'holdings', 'returns', 'allocation', 'risk'];
const observer = new IntersectionObserver((entries) => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      document.querySelectorAll('.sidebar-link').forEach(el => el.classList.remove('active'));
      document.querySelector(`.sidebar-link[data-nav="${entry.target.id}"]`)?.classList.add('active');
    }
  });
}, { rootMargin: '-40% 0px -55% 0px' });

sections.forEach(id => {
  const el = document.getElementById(id);
  if (el) observer.observe(el);
});
```

- 기존 섹션 DOM에 `id="summary" | "holdings" | "returns" | "allocation" | "risk"` 속성을 **추가만** 한다. 내부 구조/클래스는 건드리지 않는다.
- `rootMargin`은 화면 중앙 부근에 섹션이 들어올 때 활성화되도록 조정한 값.

### 6.2 모바일 offcanvas 자동 닫힘 (공통)

```javascript
document.querySelectorAll('#sidebar .sidebar-link:not(.disabled)').forEach(link => {
  link.addEventListener('click', () => {
    if (window.innerWidth < 992) {
      bootstrap.Offcanvas.getInstance(document.getElementById('sidebar'))?.hide();
    }
  });
});
```

### 6.3 detail.html 동작

- IntersectionObserver 로직은 추가하지 않는다(대시보드 섹션이 없음).
- 사이드바 마크업 + offcanvas 닫기 스크립트만 삽입.
- 활성 항목 없음 상태로 렌더된다.

### 6.4 스크롤 동작

- CSS `html { scroll-behavior: smooth; }` 한 줄로 브라우저 네이티브 부드러운 스크롤 사용. 별도 JS 필요 없음.

---

## 7. 영향 범위

| 파일 | 변경 내용 |
|------|-----------|
| `frontend/index.html` | ① 사이드바 마크업 삽입 ② Phase 1 5개 섹션에 `id` 추가 ③ 기존 navbar 축소 (기존 `#last-synced`와 로그아웃 버튼은 **삭제**하고 사이드바 footer에서만 유지 — `id` 중복 방지) ④ `<style>`에 사이드바 CSS 추가 ⑤ `<script>`에 IntersectionObserver + offcanvas 닫기 로직 추가 ⑥ `<body class="has-sidebar">` |
| `frontend/detail.html` | ① 사이드바 마크업 삽입 ② navbar에서 "← 대시보드" 버튼 제거 + 햄버거 추가 ③ `<style>`에 사이드바 CSS 추가 ④ `<script>`에 offcanvas 닫기 로직 추가 ⑤ `<body class="has-sidebar">` |

**백엔드/DB/라우터 변경 없음.** 프론트엔드 전용 변경.

### 중복에 관한 결정

사이드바 HTML/CSS/JS가 두 파일에 **중복 삽입**된다. 현재 프로젝트는 바닐라 HTML + FastAPI 정적 서빙 구조로 템플릿 엔진이나 번들러가 없어 공통화가 어렵다. `docs/requirements/overview.md`에 `frontend/assets/main.js`와 `styles.css` 분리 목표가 명시되어 있으므로, 이번 스코프에서는 **중복을 감수**하고 공통화는 향후 에셋 분리 작업과 함께 처리한다. (YAGNI — 여기서 에셋 분리까지 포함하면 "사이드바 추가"가 "프론트 리팩토링"으로 확장됨)

---

## 8. 수동 테스트 계획

### 8.1 데스크톱 (Chrome, 뷰포트 ≥ 992px)

- [ ] 사이드바가 좌측 240px 고정으로 표시되고 본문이 밀려나지 않는다.
- [ ] navbar가 숨겨진다 (`d-lg-none`).
- [ ] "개요 / 보유현황 / 수익률 / 자산배분 / 리스크" 클릭 시 해당 섹션으로 부드럽게 스크롤된다.
- [ ] 페이지를 스크롤할 때 뷰포트에 들어온 섹션의 사이드바 링크가 자동으로 활성화된다.
- [ ] 준비중 항목은 클릭되지 않고 커서가 not-allowed로 표시된다.
- [ ] 로그아웃 버튼이 정상 동작한다.
- [ ] `detail.html`에서도 사이드바가 동일하게 표시되고, 대시보드 링크 클릭 시 index.html로 이동한다.

### 8.2 모바일 (DevTools 375px 또는 실기기)

- [ ] 사이드바가 숨겨지고 상단에 햄버거 버튼이 있는 navbar가 보인다.
- [ ] 햄버거 탭 시 좌측에서 offcanvas가 슬라이드 인된다.
- [ ] offcanvas 바깥 영역 탭 또는 닫기 버튼 탭 시 닫힌다.
- [ ] 메뉴 항목 탭 시 offcanvas가 자동으로 닫히며 해당 섹션으로 이동한다.

### 8.3 detail.html

- [ ] 사이드바가 렌더되지만 활성 항목이 없다.
- [ ] "개요" 링크 탭 시 `/#summary`로 이동하여 index.html이 로드된다.

### 8.4 명시적으로 테스트하지 않는 항목

- 백엔드 API (변경 없음)
- JWT 로그인 흐름 (변경 없음)
- 차트/테이블 렌더링 (변경 없음)

---

## 9. 향후 확장 가이드

- **새 페이지 추가 시** (예: Phase 3 뉴스 리포트)
  1. `frontend/news.html` 생성, 사이드바 마크업 + CSS + 스크립트 복사.
  2. 사이드바의 "뉴스 리포트" 항목을 `<span class="disabled">`에서 `<a href="/news.html">`로 승격.
  3. 준비중 `badge` 제거.
- **에셋 분리 시점**이 오면 사이드바 HTML을 `frontend/partials/sidebar.html`로, CSS를 `frontend/assets/styles.css`로, JS를 `frontend/assets/sidebar.js`로 추출한다. 이는 별개 작업으로 진행.
