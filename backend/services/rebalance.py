"""리밸런싱 추천 로직.

현재 포트폴리오 비중과 목표 비중을 비교하여 매수/매도 추천을 생성한다.
"""
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from database import RebalanceTarget


def get_targets(db: Session) -> List[Dict[str, Any]]:
    """저장된 목표 비중 목록 반환."""
    rows = db.query(RebalanceTarget).order_by(RebalanceTarget.target_weight.desc()).all()
    return [
        {
            "id": r.id,
            "ticker": r.ticker,
            "name": r.name,
            "asset_type": r.asset_type,
            "target_weight": r.target_weight,
        }
        for r in rows
    ]


def set_targets(db: Session, targets: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """목표 비중을 일괄 저장 (기존 데이터 교체).

    targets: [{"ticker": "KRW-BTC", "name": "비트코인", "asset_type": "crypto", "target_weight": 0.4}, ...]
    """
    # 기존 목표 삭제
    db.query(RebalanceTarget).delete()
    db.flush()

    result = []
    for t in targets:
        row = RebalanceTarget(
            ticker=t["ticker"],
            name=t.get("name", t["ticker"]),
            asset_type=t.get("asset_type", "crypto"),
            target_weight=t["target_weight"],
        )
        db.add(row)
        db.flush()
        result.append({
            "id": row.id,
            "ticker": row.ticker,
            "name": row.name,
            "asset_type": row.asset_type,
            "target_weight": row.target_weight,
        })

    db.commit()
    return result


def calculate_rebalance(
    assets: List[Dict[str, Any]],
    targets: List[Dict[str, Any]],
    additional_investment: float = 0,
) -> Dict[str, Any]:
    """현재 포트폴리오와 목표 비중을 비교하여 리밸런싱 추천 생성.

    Args:
        assets: 현재 보유 자산 리스트 (포트폴리오 캐시의 assets)
        targets: 목표 비중 리스트
        additional_investment: 추가 투자 금액 (0이면 현재 자산 내에서 리밸런싱)

    Returns:
        {
            "total_value": 현재 총 평가액,
            "target_value": 목표 기준 총액 (현재 + 추가투자),
            "items": [{ticker, name, current_weight, target_weight, diff_weight, current_value, target_value, action, amount}, ...],
            "unassigned_weight": 목표에 미할당된 비중,
            "untracked_assets": 목표에 없는 보유 자산 리스트
        }
    """
    total_value = sum(a["total_value"] for a in assets)
    target_total = total_value + additional_investment

    # 현재 자산 맵: ticker -> asset
    asset_map: Dict[str, Dict] = {}
    for a in assets:
        asset_map[a["ticker"]] = a

    # 목표 티커 집합
    target_tickers = {t["ticker"] for t in targets}
    total_target_weight = sum(t["target_weight"] for t in targets)

    items = []
    for t in targets:
        ticker = t["ticker"]
        asset = asset_map.get(ticker)

        current_value = asset["total_value"] if asset else 0
        current_weight = (current_value / total_value) if total_value > 0 else 0
        target_weight = t["target_weight"]
        target_value = target_total * target_weight
        diff_value = target_value - current_value
        diff_weight = target_weight - current_weight

        if abs(diff_value) < 1000:  # 1000원 미만 변동은 무시
            action = "hold"
        elif diff_value > 0:
            action = "buy"
        else:
            action = "sell"

        current_price = asset["current_price"] if asset else 0
        diff_quantity = (diff_value / current_price) if current_price > 0 else 0

        items.append({
            "ticker": ticker,
            "name": t["name"],
            "asset_type": t.get("asset_type", "crypto"),
            "current_weight": round(current_weight, 4),
            "target_weight": round(target_weight, 4),
            "diff_weight": round(diff_weight, 4),
            "current_value": round(current_value),
            "target_value": round(target_value),
            "diff_value": round(diff_value),
            "diff_quantity": round(diff_quantity, 8),
            "current_price": round(current_price),
            "action": action,
        })

    # 목표에 없는 보유 자산
    untracked = []
    for a in assets:
        if a["ticker"] not in target_tickers:
            w = (a["total_value"] / total_value) if total_value > 0 else 0
            untracked.append({
                "ticker": a["ticker"],
                "name": a["name"],
                "current_value": round(a["total_value"]),
                "current_weight": round(w, 4),
            })

    return {
        "total_value": round(total_value),
        "target_value": round(target_total),
        "additional_investment": round(additional_investment),
        "total_target_weight": round(total_target_weight, 4),
        "unassigned_weight": round(1 - total_target_weight, 4),
        "items": sorted(items, key=lambda x: x["diff_value"]),
        "untracked_assets": untracked,
    }
