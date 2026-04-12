from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from apscheduler.schedulers.background import BackgroundScheduler

from database import AssetSnapshot, ManualAsset, PortfolioSnapshot, Session, StockHolding, engine
from services.upbit import STAKING_MAP, fetch_upbit_assets, fetch_upbit_candles
from services.stock import get_usd_krw

scheduler = BackgroundScheduler()

# 현재 포트폴리오 상태를 계산하여 메모리 캐시와 DB에 저장한다.
_portfolio_cache: Dict[str, Any] = {}
_backfill_done: bool = False


def get_portfolio_cache() -> Dict[str, Any]:
    return _portfolio_cache


def backfill_historical_snapshots(assets: List[Dict]) -> None:
    """현재 보유 자산 수량 기준으로 과거 365일 포트폴리오 가치를 역산해 DB에 삽입.

    이미 해당 날짜의 스냅샷이 있으면 건너뜀 (중복 방지).
    '현재 수량으로 과거에도 보유했다면' 기준의 시뮬레이션 데이터.
    """
    if not assets:
        return

    print("[Backfill] 과거 데이터 수집 시작...")

    # 티커별 365일 일봉 캔들 수집
    # 스테이킹 자산(ETH2 등)은 해당 마켓이 없으므로 실제 가격 티커를 사용
    staking_ticker_alias: Dict[str, str] = {
        info["ticker"]: info["price_ticker"].replace("KRW-", "")
        for info in STAKING_MAP.values()
    }  # ex: {"KRW-ETH2": "ETH"}

    ticker_prices: Dict[str, Dict[str, float]] = {}
    for asset in assets:
        ticker = asset["ticker"]
        # 스테이킹 자산이면 실제 캔들 티커로 교체 (KRW-ETH2 → KRW-ETH)
        candle_ticker = ticker
        if ticker in staking_ticker_alias:
            candle_ticker = f"KRW-{staking_ticker_alias[ticker]}"

        price_map = fetch_upbit_candles(candle_ticker, count=365)
        if price_map:
            ticker_prices[ticker] = price_map  # 원래 티커 키로 저장
            print(f"[Backfill] {ticker} (캔들: {candle_ticker}): {len(price_map)}일치 데이터 수집")

    if not ticker_prices:
        print("[Backfill] 수집된 캔들 데이터 없음. 중단.")
        return

    # 모든 자산에 데이터가 있는 날짜만 사용
    common_dates = None
    for price_map in ticker_prices.values():
        dates = set(price_map.keys())
        common_dates = dates if common_dates is None else common_dates & dates

    if not common_dates:
        print("[Backfill] 공통 날짜 없음. 중단.")
        return

    sorted_dates = sorted(common_dates)

    inserted = 0
    with Session(engine) as db:
        for date_str in sorted_dates:
            # 오늘 날짜는 실시간 sync가 담당 → 스킵
            if date_str >= datetime.utcnow().strftime("%Y-%m-%d"):
                continue

            # 해당 날짜 스냅샷이 이미 있으면 스킵
            day_start = datetime.strptime(date_str, "%Y-%m-%d")
            day_end = day_start + timedelta(days=1)
            exists = (
                db.query(PortfolioSnapshot)
                .filter(
                    PortfolioSnapshot.timestamp >= day_start,
                    PortfolioSnapshot.timestamp < day_end,
                )
                .first()
            )
            if exists:
                continue

            total_value = 0.0
            total_investment = 0.0
            for asset in assets:
                prices = ticker_prices.get(asset["ticker"])
                if not prices:
                    continue
                price = prices.get(date_str)
                if price is None:
                    continue
                total_value += asset["quantity"] * price
                total_investment += asset["quantity"] * asset["avg_price"]

            if total_value <= 0:
                continue

            total_pl = total_value - total_investment
            total_plr = (total_value / total_investment - 1) if total_investment > 0 else 0.0

            # UTC 기준 해당 날짜 00:00:00 저장 (KST 기준 날짜이므로 -9h = UTC 전날 15:00이나
            # 분석 로직은 날짜 문자열로 resample하므로 자정 UTC로 저장해도 무방)
            snapshot = PortfolioSnapshot(
                timestamp=day_start,
                total_value=total_value,
                total_profit_loss=total_pl,
                total_profit_loss_rate=total_plr,
                total_investment=total_investment,
                today_profit_loss=None,
            )
            db.add(snapshot)
            inserted += 1

        db.commit()

    print(f"[Backfill] 완료: {inserted}개 스냅샷 삽입 ({len(sorted_dates)}일 처리)")


def sync_portfolio() -> None:
    global _portfolio_cache, _backfill_done
    print(f"[{datetime.now().isoformat()}] Syncing portfolio...")

    try:
        raw_assets = fetch_upbit_assets()
    except Exception as e:
        print(f"[Sync] 업비트 데이터 조회 실패: {e}")
        # 이전 캐시 유지 (있으면), 없으면 빈 포트폴리오로 초기화
        if not _portfolio_cache:
            _portfolio_cache = {
                "last_synced": datetime.now().isoformat(),
                "total_value": 0.0,
                "total_investment": 0.0,
                "total_profit_loss": 0.0,
                "total_profit_loss_rate": 0.0,
                "today_profit_loss": None,
                "assets": [],
                "sync_error": str(e),
            }
        return

    # 수동 등록 자산 현재가 조회 후 병합
    with Session(engine) as db:
        manual_assets = db.query(ManualAsset).filter(ManualAsset.is_active == True).all()

    if manual_assets:
        manual_price_tickers = list({m.price_ticker for m in manual_assets})
        try:
            price_res = requests.get(
                f"https://api.upbit.com/v1/ticker?markets={','.join(manual_price_tickers)}",
                timeout=10,
            )
            price_res.raise_for_status()
            manual_price_map = {t["market"]: t for t in price_res.json()}
        except Exception as e:
            print(f"[Sync] 수동 자산 가격 조회 실패: {e}")
            manual_price_map = {}

        for m in manual_assets:
            ticker_data = manual_price_map.get(m.price_ticker)
            if ticker_data:
                cur_price = float(ticker_data["trade_price"])
                raw_assets.append({
                    "name": m.name,
                    "ticker": m.ticker,
                    "quantity": m.quantity,
                    "avg_price": m.avg_price,
                    "current_price": cur_price,
                    "first_purchase_date": m.first_purchase_date,
                    "signed_change_price": float(ticker_data["signed_change_price"]),
                    "signed_change_rate": float(ticker_data["signed_change_rate"]),
                })

    # 주식 보유 자산 현재가 조회 후 병합
    with Session(engine) as db:
        stock_holdings = db.query(StockHolding).filter(StockHolding.is_active == True).all()

    if stock_holdings:
        usd_krw = get_usd_krw()
        if usd_krw:
            import yfinance as yf
            for s in stock_holdings:
                try:
                    t = yf.Ticker(s.ticker)
                    info = t.info
                    cur_price_usd = info.get("currentPrice") or info.get("regularMarketPrice")
                    if cur_price_usd is None:
                        continue
                    cur_price_krw = cur_price_usd * usd_krw
                    avg_price_krw = s.avg_price * usd_krw
                    previous_close = info.get("previousClose")
                    signed_change_price = 0.0
                    signed_change_rate = 0.0
                    if previous_close and previous_close > 0:
                        signed_change_price = (cur_price_usd - previous_close) * usd_krw
                        signed_change_rate = (cur_price_usd - previous_close) / previous_close
                    raw_assets.append({
                        "name": s.name,
                        "ticker": s.ticker,
                        "quantity": s.quantity,
                        "avg_price": avg_price_krw,
                        "current_price": cur_price_krw,
                        "first_purchase_date": s.first_purchase_date,
                        "asset_type": "stock",
                        "signed_change_price": signed_change_price,
                        "signed_change_rate": signed_change_rate,
                    })
                except Exception as e:
                    print(f"[Sync] 주식 {s.ticker} 조회 실패: {e}")

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
                "asset_type": a.get("asset_type", "crypto"),
                "signed_change_price": a.get("signed_change_price", 0),
                "signed_change_rate": a.get("signed_change_rate", 0),
            }
        )

    total_pl = total_value - total_purchase
    total_plr = (total_value / total_purchase - 1) if total_purchase > 0 else 0.0

    # 오늘의 손익: 24시간 전 스냅샷 대비
    today_pl = None
    with Session(engine) as db:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        past_snapshot = (
            db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.timestamp <= cutoff)
            .order_by(PortfolioSnapshot.timestamp.desc())
            .first()
        )
        if past_snapshot and past_snapshot.total_value:
            today_pl = total_value - past_snapshot.total_value

    # 메모리 캐시 갱신
    _portfolio_cache = {
        "last_synced": datetime.now().isoformat(),
        "total_value": total_value,
        "total_investment": total_purchase,
        "total_profit_loss": total_pl,
        "total_profit_loss_rate": total_plr,
        "today_profit_loss": today_pl,
        "assets": asset_rows,
    }

    # DB 스냅샷 저장
    with Session(engine) as db:
        snapshot = PortfolioSnapshot(
            timestamp=datetime.utcnow(),
            total_value=total_value,
            total_profit_loss=total_pl,
            total_profit_loss_rate=total_plr,
            total_investment=total_purchase,
            today_profit_loss=today_pl,
        )
        db.add(snapshot)
        db.flush()
        for a in asset_rows:
            db.add(AssetSnapshot(snapshot_id=snapshot.id, **a))
        db.commit()

    print("Sync complete.")

    # 서버 시작 후 최초 1회 과거 데이터 백필
    if not _backfill_done and asset_rows:
        _backfill_done = True
        backfill_historical_snapshots(asset_rows)


def start_scheduler():
    # 서버 시작 즉시 1회 실행 후, 이후 1분 간격으로 반복
    scheduler.add_job(
        sync_portfolio,
        "interval",
        minutes=1,
        id="portfolio_sync",
        next_run_time=datetime.now(),
    )
    scheduler.start()


def stop_scheduler():
    scheduler.shutdown()
