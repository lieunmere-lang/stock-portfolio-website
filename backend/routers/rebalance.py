"""리밸런싱 추천 API 라우터."""
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from scheduler import get_portfolio_cache
from services.rebalance import calculate_rebalance, get_targets, set_targets

router = APIRouter(prefix="/api/rebalance")


class TargetItem(BaseModel):
    ticker: str
    name: str
    asset_type: str = "crypto"
    target_weight: float


class TargetsRequest(BaseModel):
    targets: List[TargetItem]


@router.get("/targets")
def api_get_targets(db: Session = Depends(get_db)) -> Dict[str, Any]:
    """저장된 목표 비중 조회."""
    targets = get_targets(db)
    return {"targets": targets}


@router.put("/targets")
def api_set_targets(req: TargetsRequest, db: Session = Depends(get_db)) -> Dict[str, Any]:
    """목표 비중 일괄 저장."""
    targets = set_targets(db, [t.model_dump() for t in req.targets])
    return {"targets": targets}


@router.get("/recommend")
def api_get_recommendation(
    additional: float = Query(default=0, ge=0, description="추가 투자 금액"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """현재 포트폴리오 기준 리밸런싱 추천."""
    cache = get_portfolio_cache()
    assets = cache.get("assets", []) if cache else []
    targets = get_targets(db)

    if not targets:
        return {"error": "목표 비중이 설정되지 않았습니다.", "items": []}

    result = calculate_rebalance(assets, targets, additional_investment=additional)
    return result
