import os
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")

# 거래 불가 스테이킹 자산 → 가격 조회에 사용할 실제 티커 매핑
# 업비트 ETH 스테이킹은 'ETH2' 통화로 잔액에 표시되지만 KRW-ETH2 마켓이 없으므로
# KRW-ETH 현재가를 그대로 사용한다.
STAKING_MAP: Dict[str, Dict[str, str]] = {
    "ETH2": {"price_ticker": "KRW-ETH", "display_name": "이더리움 (스테이킹)", "ticker": "KRW-ETH2"},
}


def fetch_upbit_assets() -> List[Dict[str, Any]]:
    """업비트 계정의 보유 코인 목록과 현재가를 반환한다."""
    if not UPBIT_ACCESS_KEY or not UPBIT_SECRET_KEY:
        print("Upbit API keys not set. Skipping fetch.")
        return []

    payload = {"access_key": UPBIT_ACCESS_KEY, "nonce": str(uuid.uuid4())}
    token = jwt.encode(payload, UPBIT_SECRET_KEY)
    headers = {"Authorization": f"Bearer {token}"}

    res = requests.get("https://api.upbit.com/v1/accounts", headers=headers, timeout=10)
    res.raise_for_status()
    my_assets = res.json()

    regular_currencies = [
        a["currency"] for a in my_assets
        if a["currency"] != "KRW" and a["currency"] not in STAKING_MAP
    ]
    staking_assets = [
        a for a in my_assets if a["currency"] in STAKING_MAP
    ]

    if not regular_currencies and not staking_assets:
        return []

    # 일반 마켓 가격 조회
    price_tickers_needed = {f"KRW-{c}" for c in regular_currencies}
    # 스테이킹 자산도 참조하는 가격 티커 추가 (ex: KRW-ETH)
    for info in STAKING_MAP.values():
        price_tickers_needed.add(info["price_ticker"])

    ticker_res = requests.get(
        f"https://api.upbit.com/v1/ticker?markets={','.join(price_tickers_needed)}",
        timeout=10,
    )
    ticker_res.raise_for_status()
    ticker_map = {t["market"]: t for t in ticker_res.json()}

    result = []

    # 일반 자산
    for asset in my_assets:
        currency = asset["currency"]
        if currency == "KRW" or currency in STAKING_MAP:
            continue
        market = f"KRW-{currency}"
        price_info = ticker_map.get(market)
        if not price_info:
            continue
        result.append(
            {
                "name": currency,
                "ticker": market,
                "quantity": float(asset["balance"]),
                "avg_price": float(asset["avg_buy_price"]),
                "current_price": float(price_info["trade_price"]),
            }
        )

    # 스테이킹 자산 (ETH2 등)
    for asset in staking_assets:
        currency = asset["currency"]
        info = STAKING_MAP[currency]
        price_info = ticker_map.get(info["price_ticker"])
        if not price_info:
            continue
        quantity = float(asset["balance"])
        avg_price = float(asset["avg_buy_price"])
        if quantity <= 0:
            continue
        result.append(
            {
                "name": info["display_name"],
                "ticker": info["ticker"],
                "quantity": quantity,
                "avg_price": avg_price,
                "current_price": float(price_info["trade_price"]),
            }
        )

    return result


def fetch_upbit_candles(ticker: str, count: int = 365) -> Dict[str, float]:
    """업비트 일봉 캔들로 {날짜: 종가} 딕셔너리 반환 (인증 불필요).

    - ticker: 'KRW-BTC' 형식
    - count: 최대 가져올 일 수 (최대 365일)
    - 반환: {"2024-01-01": 50000000.0, ...}  (KST 기준 날짜)
    """
    price_map: Dict[str, float] = {}
    to: Optional[str] = None
    remaining = min(count, 365)

    while remaining > 0:
        fetch_count = min(remaining, 200)
        params: Dict[str, Any] = {"market": ticker, "count": fetch_count}
        if to:
            params["to"] = to

        try:
            res = requests.get(
                "https://api.upbit.com/v1/candles/days",
                params=params,
                timeout=10,
            )
            res.raise_for_status()
            candles = res.json()
        except Exception as e:
            print(f"[Upbit Candle] {ticker} 조회 실패: {e}")
            break

        if not candles:
            break

        for c in candles:
            # candle_date_time_kst: "2024-01-01T09:00:00" → 날짜 부분만 사용
            date_str = c["candle_date_time_kst"][:10]
            price_map[date_str] = float(c["trade_price"])

        remaining -= len(candles)

        # 다음 페이지: 가장 오래된 캔들 1초 전
        oldest_kst = candles[-1]["candle_date_time_kst"]  # e.g. "2024-01-01T09:00:00"
        oldest_dt = datetime.strptime(oldest_kst, "%Y-%m-%dT%H:%M:%S")
        to = (oldest_dt - timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")

        if len(candles) < fetch_count:
            break

        # API 레이트 리밋 방지 (초당 10회 이하)
        time.sleep(0.12)

    return price_map
