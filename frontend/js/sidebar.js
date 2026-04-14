/**
 * 공통 사이드바 컴포넌트
 * 모든 페이지에서 동일한 사이드바를 렌더링한다.
 * 사용법: <script src="/js/sidebar.js"></script>
 */
(function () {
    const currentPath = location.pathname;

    function isActive(href) {
        if (href === '/' || href === '/index.html') {
            return currentPath === '/' || currentPath === '/index.html';
        }
        return currentPath === href;
    }

    function link(href, icon, label, opts = {}) {
        if (opts.disabled) {
            return `<span class="sidebar-link disabled">${label} <span class="badge text-bg-light">준비중</span></span>`;
        }
        const active = isActive(href) ? ' active' : '';
        return `<a href="${href}" class="sidebar-link${active}"><i class="bi bi-${icon} me-2"></i>${label}</a>`;
    }

    const sidebarHTML = `
<aside id="sidebar" class="offcanvas-lg offcanvas-start" tabindex="-1">
    <div class="offcanvas-header border-bottom">
        <span class="fw-bold"><i class="bi bi-bar-chart-line-fill text-primary"></i> My Portfolio</span>
        <button type="button" class="btn-close d-lg-none" data-bs-dismiss="offcanvas" data-bs-target="#sidebar"></button>
    </div>
    <nav class="offcanvas-body d-flex flex-column p-0">
        ${link('/', 'speedometer2', '대시보드')}

        <div class="sidebar-group-label">개인종목</div>
        <div id="sidebar-assets"></div>

        <div class="sidebar-group-label">분석</div>
        ${link('/news.html', 'newspaper', '뉴스 리포트')}
        ${link('/market.html', 'globe', '시장 상황판')}
        ${link('/liquidity.html', 'water', '유동성 흐름')}

        <div class="sidebar-group-label">도구</div>
        ${link('#', '', '가격 알림', { disabled: true })}
        ${link('/rebalance.html', 'sliders', '리밸런싱')}
        ${link('/journal.html', 'journal-text', '트레이드 저널')}
        ${link('/simulator.html', 'calculator', '복리 시뮬레이터')}

        <div class="sidebar-group-label">기타</div>
        ${link('#', '', '설정', { disabled: true })}

        <div class="sidebar-footer">
            <button onclick="logout()" class="btn btn-sm btn-outline-secondary w-100">
                <i class="bi bi-box-arrow-right"></i> 로그아웃
            </button>
        </div>
    </nav>
</aside>`;

    // 페이지 제목 매핑
    const pageTitles = {
        '/': '대시보드',
        '/index.html': '대시보드',
        '/news.html': '뉴스 리포트',
        '/market.html': '시장 상황판',
        '/rebalance.html': '리밸런싱',
        '/journal.html': '트레이드 저널',
        '/simulator.html': '복리 시뮬레이터',
        '/liquidity.html': '유동성 흐름',
        '/detail.html': '종목 상세',
    };
    const pageTitle = pageTitles[currentPath] || 'My Portfolio';

    const mobileNavHTML = `
<nav class="navbar navbar-light bg-white border-bottom px-3 py-2 d-lg-none">
    <button class="btn btn-sm" type="button"
            data-bs-toggle="offcanvas" data-bs-target="#sidebar"
            aria-controls="sidebar" aria-label="메뉴 열기">
        <i class="bi bi-list fs-4"></i>
    </button>
    <span class="fw-semibold fs-6">${pageTitle}</span>
    <span style="width:32px"></span>
</nav>`;

    // body 시작 부분에 삽입
    document.body.insertAdjacentHTML('afterbegin', sidebarHTML + mobileNavHTML);

    // 모바일에서 링크 클릭 시 offcanvas 닫기
    const sidebarEl = document.getElementById('sidebar');
    document.querySelectorAll('#sidebar .sidebar-link:not(.disabled)').forEach(el => {
        el.addEventListener('click', () => {
            if (window.innerWidth < 992 && sidebarEl) {
                const inst = bootstrap.Offcanvas.getInstance(sidebarEl)
                    || bootstrap.Offcanvas.getOrCreateInstance(sidebarEl);
                inst.hide();
            }
        });
    });
})();
