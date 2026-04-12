from datetime import datetime, timedelta
from typing import Any, Dict, List

import requests
from apscheduler.schedulers.background import BackgroundScheduler

import asyncio

from database import AssetSnapshot, ManualAsset, NewsReport, NewsReportItem, PortfolioSnapshot, RawNews, Session, StockHolding, engine
from services.upbit import STAKING_MAP, fetch_upbit_assets, fetch_upbit_candles
from services.stock import get_usd_krw
from services.market import get_sp500_list, _get_sp500_market_caps

scheduler = BackgroundScheduler()

# 현재 포트폴리오 상태를 계산하여 메모리 캐시와 DB에 저장한다.
_portfolio_cache: Dict[str, Any] = {}
_backfill_done: bool = False


def get_portfolio_cache() -> Dict[str, Any]:
    return _portfolio_cache


def backfill_historical_snapshots(assets: List[Dict]) -> None:
    """현재 보유 자산 수량 기준으로 과거 포트폴리오 가치를 역산해 DB에 삽입.

    - 암호화폐: 업비트 일봉 캔들 (최대 365일)
    - US 주식: yfinance 히스토리 + USD/KRW 환율
    - first_purchase_date 이전 날짜에는 해당 자산 제외
    - 이미 해당 날짜의 스냅샷이 있으면 건너뜀 (중복 방지)
    """
    if not assets:
        return

    print("[Backfill] 과거 데이터 수집 시작...")

    # ── 1) 암호화폐: 업비트 캔들 수집 ──
    staking_ticker_alias: Dict[str, str] = {
        info["ticker"]: info["price_ticker"].replace("KRW-", "")
        for info in STAKING_MAP.values()
    }

    ticker_prices: Dict[str, Dict[str, float]] = {}
    for asset in assets:
        ticker = asset["ticker"]
        if asset.get("asset_type", "crypto") != "crypto":
            continue
        candle_ticker = ticker
        if ticker in staking_ticker_alias:
            candle_ticker = f"KRW-{staking_ticker_alias[ticker]}"

        price_map = fetch_upbit_candles(candle_ticker, count=365)
        if price_map:
            ticker_prices[ticker] = price_map
            print(f"[Backfill] {ticker} (캔들: {candle_ticker}): {len(price_map)}일치 데이터 수집")

    # ── 2) US 주식: yfinance 히스토리 + USD/KRW 환율 ──
    stock_assets = [a for a in assets if a.get("asset_type") == "stock"]
    if stock_assets:
        import yfinance as yf

        # USD/KRW 과거 환율
        try:
            fx_hist = yf.Ticker("USDKRW=X").history(period="1y")
            fx_by_date = {d.strftime("%Y-%m-%d"): float(fx_hist["Close"].iloc[i])
                         for i, d in enumerate(fx_hist.index)}
            print(f"[Backfill] USD/KRW 환율: {len(fx_by_date)}일치 데이터 수집")
        except Exception as e:
            print(f"[Backfill] USD/KRW 환율 조회 실패: {e}")
            fx_by_date = {}

        if fx_by_date:
            for asset in stock_assets:
                ticker = asset["ticker"]
                try:
                    hist = yf.Ticker(ticker).history(period="1y")
                    if hist.empty:
                        continue
                    price_map = {}
                    for i, d in enumerate(hist.index):
                        date_str = d.strftime("%Y-%m-%d")
                        fx_rate = fx_by_date.get(date_str)
                        if fx_rate:
                            price_map[date_str] = float(hist["Close"].iloc[i]) * fx_rate
                    if price_map:
                        ticker_prices[ticker] = price_map
                        print(f"[Backfill] {ticker} (yfinance): {len(price_map)}일치 데이터 수집")
                except Exception as e:
                    print(f"[Backfill] {ticker} 조회 실패: {e}")

    if not ticker_prices:
        print("[Backfill] 수집된 데이터 없음. 중단.")
        return

    # ── 3) 주말/공휴일 갭 채우기 (직전 거래일 종가로 forward-fill) ──
    all_dates: set = set()
    for price_map in ticker_prices.values():
        all_dates |= set(price_map.keys())

    if all_dates:
        min_date = datetime.strptime(min(all_dates), "%Y-%m-%d")
        max_date = datetime.strptime(max(all_dates), "%Y-%m-%d")
        # 최소~최대 날짜 사이 모든 날짜 생성
        d = min_date
        while d <= max_date:
            all_dates.add(d.strftime("%Y-%m-%d"))
            d += timedelta(days=1)

        # 각 자산별 forward-fill: 가격 데이터가 없는 날은 직전 값 사용
        for ticker, price_map in ticker_prices.items():
            filled = {}
            sorted_all = sorted(all_dates)
            last_price = None
            for ds in sorted_all:
                if ds in price_map:
                    last_price = price_map[ds]
                if last_price is not None:
                    filled[ds] = last_price
            ticker_prices[ticker] = filled

    sorted_dates = sorted(all_dates)

    inserted = 0
    with Session(engine) as db:
        for date_str in sorted_dates:
            if date_str >= datetime.utcnow().strftime("%Y-%m-%d"):
                continue

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
                # first_purchase_date 이전이면 스킵
                fpd = asset.get("first_purchase_date")
                if fpd:
                    fpd_str = fpd.strftime("%Y-%m-%d") if isinstance(fpd, datetime) else str(fpd)[:10]
                    if date_str < fpd_str:
                        continue

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


# 업비트 자산 최초 매수일 (API에서 제공하지 않으므로 수동 매핑)
UPBIT_PURCHASE_DATES = {
    "KRW-BTC": datetime(2022, 4, 18),
}


def sync_portfolio() -> None:
    global _portfolio_cache, _backfill_done
    print(f"[{datetime.now().isoformat()}] Syncing portfolio...")

    try:
        raw_assets = fetch_upbit_assets()
        # 업비트 자산에 수동 매핑된 매수일 주입
        for a in raw_assets:
            if a["ticker"] in UPBIT_PURCHASE_DATES:
                a["first_purchase_date"] = UPBIT_PURCHASE_DATES[a["ticker"]]
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
                        "avg_price_usd": s.avg_price,
                        "current_price_usd": cur_price_usd,
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
                "first_purchase_date": a.get("first_purchase_date"),
                "avg_price_usd": a.get("avg_price_usd"),
                "current_price_usd": a.get("current_price_usd"),
            }
        )

    total_pl = total_value - total_purchase
    total_plr = (total_value / total_purchase - 1) if total_purchase > 0 else 0.0

    # 오늘의 손익: 각 자산의 당일 변동분 합산 (자산 추가/삭제에 영향받지 않음)
    today_pl = sum(a.get("signed_change_price", 0) * a["quantity"] for a in raw_assets)

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
        # DB에 저장하지 않는 필드 제외
        db_exclude = {"avg_price_usd", "current_price_usd", "first_purchase_date"}
        for a in asset_rows:
            db.add(AssetSnapshot(snapshot_id=snapshot.id, **{k: v for k, v in a.items() if k not in db_exclude}))
        db.commit()

    print("Sync complete.")

    # 서버 시작 후 최초 1회 과거 데이터 백필
    if not _backfill_done and asset_rows:
        _backfill_done = True
        backfill_historical_snapshots(asset_rows)


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
    import services.collectors.google_news
    import services.collectors.investing_calendar
    import services.collectors.alpha_vantage
    import services.collectors.fred
    import services.collectors.reuters
    import services.collectors.finviz

    from services.collectors import collect_all
    from services.news_analyzer import analyze_news

    # 1. 뉴스 수집
    try:
        raw_items = asyncio.run(collect_all())
    except RuntimeError:
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
        for h in session.query(StockHolding).filter(StockHolding.is_active == True).all():
            holdings.append({"ticker": h.ticker, "name": h.name, "profit_loss_rate": 0.0})
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

    # 5. DB 저장 (매 생성마다 별도 리포트)
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M")

    with Session(engine) as session:
        report = NewsReport(
            report_date=now_str,
            summary=report_data.get("summary", ""),
            model_used=report_data.get("model_used", ""),
            total_collected=len(raw_items),
            total_selected=len(report_data.get("items", [])),
        )
        session.add(report)
        session.flush()

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


def sync_market_caps():
    """S&P500 시가총액 일일 동기화. 매일 오전 7시 자동 실행."""
    try:
        sp500 = get_sp500_list()
        if sp500:
            tickers = [s["ticker"] for s in sp500]
            _get_sp500_market_caps(tickers)
            print(f"[Scheduler] S&P500 시가총액 동기화 완료: {len(tickers)}개")
    except Exception as e:
        print(f"[Scheduler] S&P500 시가총액 동기화 실패: {e}")


def _send_discord_notifications():
    """뉴스 리포트 생성 후 디스코드로 전송 (09:00 KST 실행)"""
    import asyncio
    try:
        from bot.client import bot
        if bot.is_ready():
            cog = bot.get_cog("FinanceCog")
            if cog:
                loop = bot.loop
                asyncio.run_coroutine_threadsafe(cog.send_news_report(), loop)
                asyncio.run_coroutine_threadsafe(cog.send_indicators(), loop)
                logger.info("Discord notifications scheduled")
            else:
                logger.warning("FinanceCog not loaded")
        else:
            logger.warning("Discord bot not ready — skipping notifications")
    except Exception as e:
        logger.error(f"Discord notification error: {e}")


def _check_price_alerts():
    """5분마다 가격 알림 체크"""
    import asyncio
    try:
        from bot.client import bot
        if bot.is_ready():
            cog = bot.get_cog("FinanceCog")
            if cog:
                loop = bot.loop
                asyncio.run_coroutine_threadsafe(cog.check_price_alerts(), loop)
    except Exception as e:
        logger.error(f"Price alert check error: {e}")


def start_scheduler():
    # 서버 시작 즉시 1회 실행 후, 이후 1분 간격으로 반복
    scheduler.add_job(
        sync_portfolio,
        "interval",
        minutes=1,
        id="portfolio_sync",
        next_run_time=datetime.now(),
    )
    scheduler.add_job(
        generate_news_report,
        "cron",
        hour=8,
        minute=50,
        timezone="Asia/Seoul",
        id="news_report",
    )
    scheduler.add_job(
        sync_market_caps,
        "interval",
        minutes=10,
        id="market_cap_sync",
        next_run_time=datetime.now(),  # 서버 시작 시 즉시 1회 실행
    )
    # 디스코드 뉴스 + 지표 전송 (09:00 KST)
    scheduler.add_job(
        _send_discord_notifications,
        "cron",
        hour=9,
        minute=0,
        timezone="Asia/Seoul",
        id="discord_notifications",
        replace_existing=True,
    )

    # 가격 알림 체크 (5분마다)
    scheduler.add_job(
        _check_price_alerts,
        "interval",
        minutes=5,
        id="check_price_alerts",
        replace_existing=True,
    )

    scheduler.start()


def stop_scheduler():
    scheduler.shutdown()
