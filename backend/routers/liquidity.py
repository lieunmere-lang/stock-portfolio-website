"""유동성 흐름 API 라우터."""
from typing import Any, Dict

from fastapi import APIRouter, Query

from services.liquidity import get_liquidity_flow

router = APIRouter(prefix="/api/liquidity")


@router.get("/flow")
def api_liquidity_flow(
    days: int = Query(default=365, ge=30, le=730),
) -> Dict[str, Any]:
    """유동성 흐름 데이터 + 코멘트 반환."""
    return get_liquidity_flow(days=days)
