# Phase 3 서브프로젝트 D: 스케줄러 + Mock 교체 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 뉴스 리포트 파이프라인을 완성한다. 스케줄러 자동 생성, 수동 트리거 API, Mock→DB 조회 교체.

**Architecture:** `scheduler.py`에 `generate_news_report()` 추가 + cron job 등록. `routers/news.py`에서 Mock 데이터를 전부 제거하고 DB 조회로 교체. `POST /api/news/generate` 수동 트리거 추가.

**Tech Stack:** Python 3.9, FastAPI, SQLAlchemy, APScheduler

**Spec:** `docs/superpowers/specs/2026-04-12-phase3-subproject-d-scheduler.md`

---

### Task 1: `scheduler.py` — `generate_news_report()` 함수 추가

**Files:**
- Modify: `backend/scheduler.py:1-11` (import 추가)
- Modify: `backend/scheduler.py:360-369` (`start_scheduler` 수정)

- [ ] **Step 1: scheduler.py 상단에 import 추가**

`backend/scheduler.py`의 기존 import 영역 (1~9행) 끝에 다음을 추가한다:

```python
import asyncio
from database import NewsReport, NewsReportItem, RawNews, ManualAsset
```

Note: `Session`, `engine`, `StockHolding`은 이미 import되어 있다.

- [ ] **Step 2: `generate_news_report()` 함수 추가**

`backend/scheduler.py`의 `start_scheduler()` 함수 직전에 다음 함수를 추가한다:

```python
def generate_news_report() -> dict:
    """뉴스를 수집하고 Claude API로 분석하여 리포트를 생성·저장한다."""
    print(f"[{datetime.now().isoformat()}] Generating news report...")

    # 수집기 등록 (import 시 @register 실행)
    import services.collectors.coindesk
    import services.collectors.cointelegraph
    import services.collectors.yahoo_finance
    import services.collectors.coingecko
    import services.collectors.sec_edgar
    import services.collectors.fear_greed

    from services.collectors import collect_all
    from services.news_analyzer import analyze_news

    # 1. 뉴스 수집
    raw_items = asyncio.get_event_loop().run_until_complete(collect_all()) if asyncio.get_event_loop().is_running() else asyncio.run(collect_all())

    try:
        raw_items = asyncio.run(collect_all())
    except RuntimeError:
        # 이미 이벤트 루프가 돌고 있으면 (FastAPI 내부 등)
        loop = asyncio.new_event_loop()
        raw_items = loop.run_until_complete(collect_all())
        loop.close()

    print(f"[NewsReport] Collected {len(raw_items)} raw items")

    # 2. 원시 뉴스 DB 저장
    with Session(engine) as session:
        for item in raw_items:
            session.add(RawNews(
                source=item.source,
                title=item.title,
                content=item.content,
                url=item.url,
                published_at=item.published_at,
            ))
        session.commit()

    # 3. 보유 종목 조회
    holdings = []
    with Session(engine) as session:
        # 미국 주식
        for h in session.query(StockHolding).filter(StockHolding.is_active == True).all():
            holdings.append({"ticker": h.ticker, "name": h.name, "profit_loss_rate": 0.0})
        # 수동 등록 자산 (크립토 스테이킹 등)
        for m in session.query(ManualAsset).filter(ManualAsset.is_active == True).all():
            holdings.append({"ticker": m.ticker, "name": m.name, "profit_loss_rate": 0.0})

    # 캐시에서 수익률 가져오기
    cached = _portfolio_cache.get("assets", [])
    rate_map = {a["ticker"]: a.get("profit_loss_rate", 0) for a in cached}
    for h in holdings:
        h["profit_loss_rate"] = rate_map.get(h["ticker"], 0.0)

    # 4. Claude 분석
    try:
        report_data = asyncio.run(analyze_news(raw_items, holdings))
    except RuntimeError:
        loop = asyncio.new_event_loop()
        report_data = loop.run_until_complete(analyze_news(raw_items, holdings))
        loop.close()

    if not report_data.get("items"):
        print("[NewsReport] Analysis returned empty report")
        return report_data

    # 5. DB 저장 (오늘 날짜 리포트가 있으면 덮어쓰기)
    today = datetime.now().strftime("%Y-%m-%d")

    with Session(engine) as session:
        existing = session.query(NewsReport).filter(NewsReport.report_date == today).first()
        if existing:
            session.delete(existing)
            session.commit()

        report = NewsReport(
            report_date=today,
            summary=report_data.get("summary", ""),
            model_used=report_data.get("model_used", ""),
            total_collected=len(raw_items),
            total_selected=len(report_data.get("items", [])),
        )
        session.add(report)
        session.flush()  # report.id 할당

        for item_data in report_data.get("items", []):
            session.add(NewsReportItem(
                report_id=report.id,
                category=item_data.get("category"),
                title=item_data.get("title"),
                summary=item_data.get("summary"),
                impact_analysis=item_data.get("impact_analysis"),
                related_ticker=item_data.get("related_ticker"),
                source=item_data.get("source"),
                source_url=item_data.get("source_url"),
                importance=item_data.get("importance"),
            ))
        session.commit()

    print(f"[NewsReport] Report saved: {today}, {len(report_data.get('items', []))} items")
    return report_data
```

- [ ] **Step 3: `start_scheduler()`에 뉴스 리포트 cron job 추가**

`backend/scheduler.py`의 `start_scheduler()` 함수 안에, `scheduler.start()` 직전에 다음을 추가한다:

```python
    scheduler.add_job(
        generate_news_report,
        "cron",
        hour=8,
        minute=50,
        timezone="Asia/Seoul",
        id="news_report",
    )
```

- [ ] **Step 4: 커밋**

```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
git add backend/scheduler.py
git commit -m "feat(scheduler): add daily news report generation job"
```

---

### Task 2: `news.py` — Mock 제거 + DB 조회 + 수동 트리거

**Files:**
- Modify: `backend/routers/news.py` (전체 교체)

- [ ] **Step 1: news.py를 다음 내용으로 전체 교체**

`backend/routers/news.py`를 다음 내용으로 **전체 교체**한다:

```python
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import NewsReport, NewsReportItem, engine
from routers.auth import verify_token

router = APIRouter(prefix="/api/news")


def require_auth(request: Request) -> str:
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header.removeprefix("Bearer ").strip()
    return verify_token(token)


def _report_to_dict(report: NewsReport) -> dict:
    """NewsReport ORM 객체를 API 응답 dict로 변환한다."""
    return {
        "report_date": report.report_date,
        "created_at": report.created_at.isoformat() if report.created_at else None,
        "model_used": report.model_used,
        "total_collected": report.total_collected,
        "total_selected": report.total_selected,
        "summary": report.summary,
        "market_indicators": None,
        "items": [
            {
                "id": item.id,
                "category": item.category,
                "title": item.title,
                "summary": item.summary,
                "impact_analysis": item.impact_analysis,
                "related_ticker": item.related_ticker,
                "source": item.source,
                "source_url": item.source_url,
                "importance": item.importance,
            }
            for item in report.items
        ],
    }


@router.get("/latest")
def get_latest_report(user: str = Depends(require_auth)):
    """최신 뉴스 리포트 조회"""
    with Session(engine) as session:
        report = (
            session.query(NewsReport)
            .order_by(NewsReport.created_at.desc())
            .first()
        )
        if not report:
            raise HTTPException(status_code=404, detail="리포트가 없습니다.")
        return _report_to_dict(report)


@router.get("/report/{report_date}")
def get_report_by_date(report_date: str, user: str = Depends(require_auth)):
    """특정 날짜 뉴스 리포트 조회"""
    with Session(engine) as session:
        report = (
            session.query(NewsReport)
            .filter(NewsReport.report_date == report_date)
            .first()
        )
        if not report:
            raise HTTPException(status_code=404, detail="해당 날짜의 리포트가 없습니다.")
        return _report_to_dict(report)


@router.get("/reports")
def list_reports(
    offset: int = 0,
    limit: int = 10,
    user: str = Depends(require_auth),
):
    """뉴스 리포트 목록 조회 (페이지네이션)"""
    with Session(engine) as session:
        total = session.query(NewsReport).count()
        reports = (
            session.query(NewsReport)
            .order_by(NewsReport.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        items = [
            {
                "report_date": r.report_date,
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "model_used": r.model_used,
                "total_collected": r.total_collected,
                "total_selected": r.total_selected,
                "summary_preview": (r.summary or "")[:60] + "..." if r.summary and len(r.summary) > 60 else r.summary,
            }
            for r in reports
        ]
        return {
            "items": items,
            "total": total,
            "has_more": offset + limit < total,
        }


@router.post("/generate")
def generate_report(user: str = Depends(require_auth)):
    """수동으로 뉴스 리포트를 즉시 생성한다."""
    from scheduler import generate_news_report
    try:
        report_data = generate_news_report()
        return {"status": "ok", "report": report_data}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"리포트 생성 실패: {str(e)}")
```

- [ ] **Step 2: 서버 재시작 후 확인**

Run:
```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
./manage_server.sh stop && ./manage_server.sh start
```

`http://localhost:8000/news.html` 접속 — 리포트가 없으면 빈 상태("아직 생성된 리포트가 없습니다") 표시됨을 확인.

- [ ] **Step 3: 커밋**

```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
git add backend/routers/news.py
git commit -m "feat(api): replace mock news data with DB queries, add POST /generate endpoint"
```

---

### Task 3: 프론트엔드 — 404 응답 처리 + 수동 생성 버튼

**Files:**
- Modify: `frontend/news.html`

현재 프론트엔드의 `loadReport()` 함수는 API가 항상 데이터를 반환한다고 가정한다. DB가 비어있으면 404가 오므로 이를 처리해야 한다.

- [ ] **Step 1: `loadReport` 함수에 404 처리 추가**

`frontend/news.html`의 `loadReport` 함수 (약 527행)의 catch 블록에서 404를 빈 상태로 처리한다. 현재:

```javascript
    } catch(e) {
        console.error('load report error:', e);
        document.getElementById('empty-state').classList.remove('d-none');
```

이 부분은 이미 빈 상태를 표시하므로 변경 불필요. 다만 `summary-card`와 `indicators-row`도 숨겨야 한다. 현재 코드를 확인하고 이미 숨기고 있으면 변경 없음.

- [ ] **Step 2: 빈 상태에 수동 생성 버튼 추가**

`frontend/news.html`의 `<!-- 빈 상태 -->` div (약 354행)를 다음으로 교체한다:

```html
    <!-- 빈 상태 -->
    <div id="empty-state" class="text-center py-5 d-none">
        <i class="bi bi-newspaper text-muted" style="font-size:3rem;"></i>
        <p class="text-muted mt-3" style="font-size:.95rem;">아직 생성된 리포트가 없습니다</p>
        <button id="btn-generate" class="btn btn-primary btn-sm mt-2" onclick="generateReport()">
            <i class="bi bi-magic"></i> 리포트 생성
        </button>
        <div id="generate-status" class="text-muted mt-2 d-none" style="font-size:.82rem;"></div>
    </div>
```

- [ ] **Step 3: `generateReport()` JS 함수 추가**

`frontend/news.html`의 `<script>` 내부, `switchView` 함수 앞에 다음 함수를 추가한다:

```javascript
// ── Manual report generation ────────────────────────────────────────────────
async function generateReport() {
    const btn = document.getElementById('btn-generate');
    const status = document.getElementById('generate-status');
    btn.disabled = true;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-1"></span>생성 중...';
    status.classList.remove('d-none');
    status.textContent = '뉴스 수집 및 분석 중입니다. 1~2분 소요됩니다...';

    try {
        const headers = getAuthHeaders();
        if (!headers) return;
        const res = await fetch('/api/news/generate', { method: 'POST', headers });
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.detail || `HTTP ${res.status}`);
        }
        status.textContent = '리포트가 생성되었습니다!';
        status.classList.remove('text-muted');
        status.classList.add('text-success');
        // 1초 후 리포트 로드
        setTimeout(() => {
            document.getElementById('empty-state').classList.add('d-none');
            loadReport();
            loadReportsList();
        }, 1000);
    } catch (e) {
        status.textContent = '생성 실패: ' + e.message;
        status.classList.remove('text-muted');
        status.classList.add('text-danger');
        btn.disabled = false;
        btn.innerHTML = '<i class="bi bi-magic"></i> 리포트 생성';
    }
}
```

- [ ] **Step 4: 커밋**

```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
git add frontend/news.html
git commit -m "feat(frontend): handle empty report state with manual generate button"
```

---

### Task 4: 통합 확인

**Files:** 없음 (수동 확인)

- [ ] **Step 1: 서버 재시작**

Run:
```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
./manage_server.sh stop && ./manage_server.sh start
```

- [ ] **Step 2: 전체 플로우 확인**

1. `/news.html` 접속 → "아직 생성된 리포트가 없습니다" + "리포트 생성" 버튼 표시
2. "리포트 생성" 버튼 클릭 → 로딩 → 리포트 표시 (ANTHROPIC_API_KEY가 설정되어 있어야 함)
3. [목록] 버튼 → 리스트 뷰에 방금 생성된 리포트 표시
4. `/` 대시보드 → 뉴스 미리보기 카드에 리포트 표시
5. 서버 로그에서 스케줄러 등록 확인: `news_report` job이 08:50 KST로 등록됨
