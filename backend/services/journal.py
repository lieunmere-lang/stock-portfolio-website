"""매매일지 서비스 — 업비트 거래내역 자동 가져오기 + CRUD."""
import os
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
import requests
from dotenv import load_dotenv
from hashlib import sha512
from urllib.parse import urlencode, unquote
from sqlalchemy.orm import Session

from database import TradeRecord

load_dotenv()

UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")


def _upbit_auth_header(query_params: Optional[Dict] = None) -> Dict[str, str]:
    """업비트 API 인증 헤더 생성."""
    payload = {
        "access_key": UPBIT_ACCESS_KEY,
        "nonce": str(uuid.uuid4()),
    }
    if query_params:
        query_string = unquote(urlencode(query_params, doseq=True))
        m = sha512()
        m.update(query_string.encode())
        payload["query_hash"] = m.hexdigest()
        payload["query_hash_alg"] = "SHA512"

    token = jwt.encode(payload, UPBIT_SECRET_KEY)
    return {"Authorization": f"Bearer {token}"}


def sync_upbit_trades(db: Session, days: int = 90) -> Dict[str, Any]:
    """업비트 체결 내역을 가져와 DB에 저장한다.

    - 최근 N일 내 체결된 주문을 조회
    - 이미 저장된 trade_id는 건너뜀 (중복 방지)
    - 반환: {"imported": 신규건수, "skipped": 중복건수, "total": 조회건수}
    """
    if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
        return {"error": "업비트 API 키가 설정되지 않았습니다.", "imported": 0, "skipped": 0, "total": 0}

    imported = 0
    skipped = 0
    total = 0
    page = 1

    while True:
        params = {
            "state": "done",
            "limit": 100,
            "page": page,
            "order_by": "desc",
        }
        headers = _upbit_auth_header(params)

        try:
            res = requests.get(
                "https://api.upbit.com/v1/orders/closed",
                params=params,
                headers=headers,
                timeout=15,
            )
            res.raise_for_status()
            orders = res.json()
        except Exception as e:
            print(f"[Journal] 업비트 주문 내역 조회 실패: {e}")
            break

        if not orders:
            break

        cutoff = datetime.utcnow() - timedelta(days=days)

        for order in orders:
            created = datetime.fromisoformat(order["created_at"].replace("+09:00", "+09:00").replace("T", "T"))
            # 간단한 ISO 파싱
            try:
                created = datetime.fromisoformat(order["created_at"].replace("+09:00", ""))
            except Exception:
                created = datetime.utcnow()

            if created < cutoff:
                # 기간 초과 → 루프 종료
                orders = []  # 외부 while도 종료되게
                break

            order_id = order.get("uuid", "")
            total += 1

            # 중복 체크
            exists = db.query(TradeRecord).filter(TradeRecord.trade_id == order_id).first()
            if exists:
                skipped += 1
                continue

            side = "buy" if order["side"] == "bid" else "sell"
            executed_volume = float(order.get("executed_volume", 0))
            if executed_volume <= 0:
                skipped += 1
                continue

            # 체결 금액과 평균 단가 계산
            paid_fee = float(order.get("paid_fee", 0))
            executed_funds = float(order.get("executed_funds", 0))
            avg_price = (executed_funds / executed_volume) if executed_volume > 0 else 0

            market = order.get("market", "")
            currency = market.replace("KRW-", "") if market.startswith("KRW-") else market

            record = TradeRecord(
                trade_id=order_id,
                ticker=market,
                name=currency,
                side=side,
                price=avg_price,
                quantity=executed_volume,
                total_amount=executed_funds,
                fee=paid_fee,
                asset_type="crypto",
                source="upbit",
                traded_at=created,
            )
            db.add(record)
            imported += 1

        if not orders:
            break
        page += 1

        # API 속도 제한 방지
        import time
        time.sleep(0.15)

    db.commit()
    return {"imported": imported, "skipped": skipped, "total": total}


def get_trades(
    db: Session,
    ticker: Optional[str] = None,
    side: Optional[str] = None,
    days: Optional[int] = None,
    limit: int = 100,
    offset: int = 0,
) -> Dict[str, Any]:
    """매매 기록 조회 (필터/페이징 지원)."""
    query = db.query(TradeRecord).order_by(TradeRecord.traded_at.desc())

    if ticker:
        query = query.filter(TradeRecord.ticker == ticker)
    if side:
        query = query.filter(TradeRecord.side == side)
    if days:
        cutoff = datetime.utcnow() - timedelta(days=days)
        query = query.filter(TradeRecord.traded_at >= cutoff)

    total_count = query.count()
    records = query.offset(offset).limit(limit).all()

    items = [
        {
            "id": r.id,
            "trade_id": r.trade_id,
            "ticker": r.ticker,
            "name": r.name,
            "side": r.side,
            "price": r.price,
            "quantity": r.quantity,
            "total_amount": r.total_amount,
            "fee": r.fee,
            "asset_type": r.asset_type,
            "source": r.source,
            "traded_at": r.traded_at.isoformat() if r.traded_at else None,
            "memo": r.memo,
        }
        for r in records
    ]

    return {"items": items, "total": total_count, "limit": limit, "offset": offset}


def get_trade_summary(db: Session, ticker: Optional[str] = None) -> Dict[str, Any]:
    """매매 요약 통계: 종목별 총 매수/매도 금액, 실현 손익 등."""
    query = db.query(TradeRecord)
    if ticker:
        query = query.filter(TradeRecord.ticker == ticker)

    records = query.order_by(TradeRecord.traded_at.asc()).all()
    if not records:
        return {"tickers": [], "summary": {}, "totals": {"buy_amount": 0, "sell_amount": 0, "fee_total": 0, "trade_count": 0}}

    # 종목별 집계
    by_ticker: Dict[str, Dict] = {}
    for r in records:
        t = r.ticker
        if t not in by_ticker:
            by_ticker[t] = {
                "ticker": t,
                "name": r.name or t,
                "buy_amount": 0,
                "sell_amount": 0,
                "buy_quantity": 0,
                "sell_quantity": 0,
                "fee_total": 0,
                "trade_count": 0,
                "first_trade": r.traded_at.isoformat() if r.traded_at else None,
                "last_trade": None,
            }
        s = by_ticker[t]
        if r.side == "buy":
            s["buy_amount"] += r.total_amount
            s["buy_quantity"] += r.quantity
        else:
            s["sell_amount"] += r.total_amount
            s["sell_quantity"] += r.quantity
        s["fee_total"] += r.fee or 0
        s["trade_count"] += 1
        s["last_trade"] = r.traded_at.isoformat() if r.traded_at else s["last_trade"]

    # 실현 손익 계산 (매도금액 - 매수금액의 비례 부분)
    for s in by_ticker.values():
        if s["sell_quantity"] > 0 and s["buy_quantity"] > 0:
            avg_buy_price = s["buy_amount"] / s["buy_quantity"]
            s["realized_pnl"] = round(s["sell_amount"] - (avg_buy_price * s["sell_quantity"]) - s["fee_total"])
        else:
            s["realized_pnl"] = 0
        s["buy_amount"] = round(s["buy_amount"])
        s["sell_amount"] = round(s["sell_amount"])
        s["fee_total"] = round(s["fee_total"])

    totals = {
        "buy_amount": sum(s["buy_amount"] for s in by_ticker.values()),
        "sell_amount": sum(s["sell_amount"] for s in by_ticker.values()),
        "fee_total": sum(s["fee_total"] for s in by_ticker.values()),
        "trade_count": sum(s["trade_count"] for s in by_ticker.values()),
        "realized_pnl": sum(s["realized_pnl"] for s in by_ticker.values()),
    }

    return {
        "tickers": sorted(by_ticker.keys()),
        "summary": by_ticker,
        "totals": totals,
    }


def add_manual_trade(db: Session, data: Dict[str, Any]) -> Dict[str, Any]:
    """수동 매매 기록 추가."""
    record = TradeRecord(
        trade_id=None,
        ticker=data["ticker"],
        name=data.get("name", data["ticker"]),
        side=data["side"],
        price=data["price"],
        quantity=data["quantity"],
        total_amount=data["price"] * data["quantity"],
        fee=data.get("fee", 0),
        asset_type=data.get("asset_type", "crypto"),
        source="manual",
        traded_at=datetime.fromisoformat(data["traded_at"]) if isinstance(data.get("traded_at"), str) else data.get("traded_at", datetime.utcnow()),
        memo=data.get("memo"),
    )
    db.add(record)
    db.commit()
    return {"id": record.id, "status": "created"}


def delete_trade(db: Session, trade_id: int) -> bool:
    """매매 기록 삭제."""
    record = db.query(TradeRecord).filter(TradeRecord.id == trade_id).first()
    if not record:
        return False
    db.delete(record)
    db.commit()
    return True
