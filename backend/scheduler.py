from datetime import datetime
from typing import Any, Dict, List

from apscheduler.schedulers.background import BackgroundScheduler

from database import AssetSnapshot, PortfolioSnapshot, Session, engine
from services.upbit import fetch_upbit_assets

scheduler = BackgroundScheduler()

# 현재 포트폴리오 상태를 계산하여 메모리 캐시와 DB에 저장한다.
_portfolio_cache: Dict[str, Any] = {}


def get_portfolio_cache() -> Dict[str, Any]:
    return _portfolio_cache


def sync_portfolio() -> None:
    global _portfolio_cache
    print(f"[{datetime.now().isoformat()}] Syncing portfolio...")

    raw_assets = fetch_upbit_assets()

    total_value = 0.0
    total_purchase = 0.0
    asset_rows = []

    for a in raw_assets:
        qty = a["quantity"]
        avg = a["avg_price"]
        cur = a["current_price"]
        val = qty * cur
        pl = (cur - avg) * qty
        plr = (cur / avg - 1) if avg > 0 else 0.0

        total_value += val
        total_purchase += qty * avg
        asset_rows.append(
            {
                "name": a["name"],
                "ticker": a["ticker"],
                "quantity": qty,
                "avg_price": avg,
                "current_price": cur,
                "total_value": val,
                "profit_loss": pl,
                "profit_loss_rate": plr,
                "asset_type": "crypto",
            }
        )

    total_pl = total_value - total_purchase
    total_plr = (total_value / total_purchase - 1) if total_purchase > 0 else 0.0

    # 메모리 캐시 갱신
    _portfolio_cache = {
        "last_synced": datetime.now().isoformat(),
        "total_value": total_value,
        "total_profit_loss": total_pl,
        "total_profit_loss_rate": total_plr,
        "assets": asset_rows,
    }

    # DB 스냅샷 저장
    with Session(engine) as db:
        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            total_value=total_value,
            total_profit_loss=total_pl,
            total_profit_loss_rate=total_plr,
        )
        db.add(snapshot)
        db.flush()
        for a in asset_rows:
            db.add(AssetSnapshot(snapshot_id=snapshot.id, **a))
        db.commit()

    print("Sync complete.")


def start_scheduler():
    scheduler.add_job(sync_portfolio, "interval", hours=1, id="portfolio_sync")
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown()
