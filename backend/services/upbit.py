import os
import uuid
from typing import Any, Dict, List

import jwt
import requests
from dotenv import load_dotenv

load_dotenv()

UPBIT_ACCESS_KEY = os.getenv("UPBIT_ACCESS_KEY")
UPBIT_SECRET_KEY = os.getenv("UPBIT_SECRET_KEY")


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

    tickers = [a["currency"] for a in my_assets if a["currency"] != "KRW"]
    if not tickers:
        return []

    upbit_tickers = [f"KRW-{t}" for t in tickers]
    ticker_res = requests.get(
        f"https://api.upbit.com/v1/ticker?markets={','.join(upbit_tickers)}",
        timeout=10,
    )
    ticker_res.raise_for_status()
    ticker_map = {t["market"]: t for t in ticker_res.json()}

    result = []
    for asset in my_assets:
        currency = asset["currency"]
        if currency == "KRW":
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
    return result
