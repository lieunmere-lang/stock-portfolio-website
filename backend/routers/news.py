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
