"""포트폴리오 분석 로직 — 수익률, 리스크 지표, 상관관계"""
import math
import statistics
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from sqlalchemy.orm import Session as DBSession

from database import AssetSnapshot, PortfolioSnapshot

# 무위험이자율 (한국 기준금리 기반 연 3.5%)
RISK_FREE_RATE = 0.035

# Upbit 티커 → CoinGecko ID 매핑
UPBIT_TO_COINGECKO: Dict[str, str] = {
    "KRW-BTC": "bitcoin",
    "KRW-ETH": "ethereum",
    "KRW-XRP": "ripple",
    "KRW-ADA": "cardano",
    "KRW-DOT": "polkadot",
    "KRW-SOL": "solana",
    "KRW-DOGE": "dogecoin",
    "KRW-MATIC": "matic-network",
    "KRW-LINK": "chainlink",
    "KRW-AVAX": "avalanche-2",
    "KRW-ATOM": "cosmos",
    "KRW-TRX": "tron",
    "KRW-NEAR": "near",
    "KRW-LTC": "litecoin",
    "KRW-ETC": "ethereum-classic",
    "KRW-BCH": "bitcoin-cash",
    "KRW-EOS": "eos",
    "KRW-XLM": "stellar",
    "KRW-ALGO": "algorand",
    "KRW-FTM": "fantom",
    "KRW-SAND": "the-sandbox",
    "KRW-MANA": "decentraland",
    "KRW-AXS": "axie-infinity",
    "KRW-SHIB": "shiba-inu",
    "KRW-UNI": "uniswap",
    "KRW-AAVE": "aave",
    "KRW-CRO": "crypto-com-chain",
    "KRW-VET": "vechain",
    "KRW-THETA": "theta-token",
    "KRW-HBAR": "hedera-hashgraph",
    "KRW-ICP": "internet-computer",
    "KRW-FIL": "filecoin",
    "KRW-APT": "aptos",
    "KRW-ARB": "arbitrum",
    "KRW-OP": "optimism",
    "KRW-SUI": "sui",
    "KRW-INJ": "injective-protocol",
    "KRW-SEI": "sei-network",
    "KRW-TIA": "celestia",
    "KRW-STX": "blockstack",
    "KRW-FLOW": "flow",
}

COINGECKO_BASE = "https://api.coingecko.com/api/v3"
COINGECKO_TIMEOUT = 10


# ── DB 기반 분석 ──────────────────────────────────────────────────────────────

def get_period_returns(db: DBSession, current_value: float) -> Dict[str, Optional[float]]:
    """DB 스냅샷으로 기간별 수익률 계산 (1d, 1w, 1m, 3m, 6m, 1y)."""
    periods = {
        "1d": timedelta(days=1),
        "1w": timedelta(weeks=1),
        "1m": timedelta(days=30),
        "3m": timedelta(days=90),
        "6m": timedelta(days=180),
        "1y": timedelta(days=365),
    }
    results: Dict[str, Optional[float]] = {}
    for key, delta in periods.items():
        target_time = datetime.utcnow() - delta
        snap = (
            db.query(PortfolioSnapshot)
            .filter(PortfolioSnapshot.timestamp <= target_time)
            .order_by(PortfolioSnapshot.timestamp.desc())
            .first()
        )
        if snap and snap.total_value and snap.total_value > 0:
            results[key] = (current_value - snap.total_value) / snap.total_value
        else:
            results[key] = None
    return results


def get_history(db: DBSession, days: int = 365) -> Dict[str, List]:
    """DB 스냅샷을 날짜별 마지막 값으로 리샘플링해 반환.

    - 하루에 스냅샷이 여러 개 있어도 그날 가장 마지막 값만 사용한다.
    - 동기화 시마다 차트가 흔들리지 않도록 일별 데이터로 안정화.
    - timestamps는 "YYYY-MM-DD" 형식으로 반환 (가로축 포맷 용이).
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.timestamp >= cutoff)
        .order_by(PortfolioSnapshot.timestamp.asc())
        .all()
    )

    if not snapshots:
        return {"timestamps": [], "values": [], "cumulative_returns": []}

    # 날짜별 마지막 스냅샷 (asc 정렬이므로 덮어쓰면 자연스럽게 마지막 값이 남음)
    daily: Dict[str, float] = {}
    for s in snapshots:
        day_key = s.timestamp.strftime("%Y-%m-%d")
        daily[day_key] = s.total_value

    sorted_days = sorted(daily.keys())
    values = [daily[d] for d in sorted_days]

    base = values[0] if values[0] else 1
    cumulative_returns = [(v - base) / base for v in values]

    return {
        "timestamps": sorted_days,   # "YYYY-MM-DD" 형식
        "values": values,
        "cumulative_returns": cumulative_returns,
    }


def calculate_mdd(db: DBSession, days: int = 365) -> Optional[float]:
    """최대 낙폭(MDD) 계산. 음수로 반환 (예: -0.15 = -15%)."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.timestamp >= cutoff)
        .order_by(PortfolioSnapshot.timestamp.asc())
        .all()
    )
    if len(snapshots) < 2:
        return None

    values = [s.total_value for s in snapshots]
    max_dd = 0.0
    peak = values[0]
    for v in values:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

    return -max_dd


def calculate_volatility_and_sharpe(
    db: DBSession, days: int = 30
) -> Dict[str, Optional[float]]:
    """일별 수익률의 표준편차(변동성)와 샤프 지수 계산."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    snapshots = (
        db.query(PortfolioSnapshot)
        .filter(PortfolioSnapshot.timestamp >= cutoff)
        .order_by(PortfolioSnapshot.timestamp.asc())
        .all()
    )

    if len(snapshots) < 3:
        return {"volatility": None, "sharpe": None}

    values = [s.total_value for s in snapshots]
    # 시간 간격이 1시간 단위이므로 일별로 집계
    daily_values = _resample_daily(snapshots)
    if len(daily_values) < 3:
        return {"volatility": None, "sharpe": None}

    daily_returns = [
        (daily_values[i] - daily_values[i - 1]) / daily_values[i - 1]
        for i in range(1, len(daily_values))
        if daily_values[i - 1] > 0
    ]
    if len(daily_returns) < 2:
        return {"volatility": None, "sharpe": None}

    vol = statistics.stdev(daily_returns)
    annualized_vol = vol * math.sqrt(252)
    annualized_return = statistics.mean(daily_returns) * 252
    sharpe = (annualized_return - RISK_FREE_RATE) / annualized_vol if annualized_vol > 0 else None

    return {
        "volatility": annualized_vol,
        "sharpe": sharpe,
    }


def _resample_daily(snapshots) -> List[float]:
    """시간별 스냅샷을 날짜별 마지막 값으로 집계."""
    daily: Dict[str, float] = {}
    for s in snapshots:
        day_key = s.timestamp.strftime("%Y-%m-%d")
        daily[day_key] = s.total_value
    return list(daily.values())


def calculate_hhi(assets: List) -> float:
    """HHI(허핀달-허슈만 지수) = Σ(비중²) × 10000. 0~10000 범위."""
    total = sum(a["total_value"] for a in assets)
    if total == 0:
        return 0.0
    return sum((a["total_value"] / total) ** 2 for a in assets) * 10000


def get_top5_contributors(assets: List) -> List[Dict]:
    """수익 기여도 상위 5개 종목."""
    sorted_assets = sorted(assets, key=lambda a: a["profit_loss"], reverse=True)
    total_value = sum(a["total_value"] for a in assets) or 1
    return [
        {
            "ticker": a["ticker"],
            "name": a["name"],
            "profit_loss": a["profit_loss"],
            "profit_loss_rate": a["profit_loss_rate"],
            "weight": a["total_value"] / total_value,
            "total_value": a["total_value"],
        }
        for a in sorted_assets[:5]
    ]


# ── CoinGecko API 기반 분석 ───────────────────────────────────────────────────

def _fetch_coingecko_prices(coin_id: str, days: int = 30) -> Optional[List[float]]:
    """CoinGecko에서 일별 종가 리스트 반환. 실패 시 None."""
    try:
        url = f"{COINGECKO_BASE}/coins/{coin_id}/market_chart"
        res = requests.get(
            url,
            params={"vs_currency": "krw", "days": days, "interval": "daily"},
            timeout=COINGECKO_TIMEOUT,
        )
        res.raise_for_status()
        data = res.json()
        prices = [p[1] for p in data.get("prices", [])]
        return prices if len(prices) >= 2 else None
    except Exception as e:
        print(f"[CoinGecko] {coin_id} 가격 조회 실패: {e}")
        return None


def calculate_beta(assets: List, days: int = 30) -> Optional[float]:
    """포트폴리오 베타 (BTC 대비). 데이터 부족 시 None."""
    tickers = [a["ticker"] for a in assets]
    btc_prices = _fetch_coingecko_prices("bitcoin", days)
    if not btc_prices or len(btc_prices) < 3:
        return None

    btc_returns = [
        (btc_prices[i] - btc_prices[i - 1]) / btc_prices[i - 1]
        for i in range(1, len(btc_prices))
    ]

    # 포트폴리오 가중 수익률 합산
    total_value = sum(a["total_value"] for a in assets) or 1
    portfolio_returns_by_day: Optional[List[float]] = None

    for asset in assets:
        cg_id = UPBIT_TO_COINGECKO.get(asset["ticker"])
        if not cg_id:
            continue
        prices = _fetch_coingecko_prices(cg_id, days)
        if not prices or len(prices) < len(btc_prices):
            continue

        weight = asset["total_value"] / total_value
        asset_returns = [
            (prices[i] - prices[i - 1]) / prices[i - 1] * weight
            for i in range(1, min(len(prices), len(btc_prices)))
        ]

        if portfolio_returns_by_day is None:
            portfolio_returns_by_day = asset_returns
        else:
            for j in range(min(len(portfolio_returns_by_day), len(asset_returns))):
                portfolio_returns_by_day[j] += asset_returns[j]

    if not portfolio_returns_by_day or len(portfolio_returns_by_day) < 3:
        return None

    n = min(len(portfolio_returns_by_day), len(btc_returns))
    p_ret = portfolio_returns_by_day[:n]
    m_ret = btc_returns[:n]

    cov = _covariance(p_ret, m_ret)
    var_m = _variance(m_ret)
    if var_m == 0:
        return None

    return cov / var_m


def calculate_correlation_matrix(assets: List, days: int = 30) -> Optional[Dict]:
    """보유 코인 간 상관관계 매트릭스. {tickers: [...], matrix: [[...]]}"""
    tickers = []
    returns_map: Dict[str, List[float]] = {}

    for asset in assets:
        cg_id = UPBIT_TO_COINGECKO.get(asset["ticker"])
        if not cg_id:
            continue
        prices = _fetch_coingecko_prices(cg_id, days)
        if not prices or len(prices) < 3:
            continue
        ret = [
            (prices[i] - prices[i - 1]) / prices[i - 1]
            for i in range(1, len(prices))
        ]
        tickers.append(asset["ticker"])
        returns_map[asset["ticker"]] = ret

    if len(tickers) < 2:
        return None

    # 공통 최소 길이로 자르기
    min_len = min(len(returns_map[t]) for t in tickers)
    for t in tickers:
        returns_map[t] = returns_map[t][:min_len]

    matrix = []
    for t1 in tickers:
        row = []
        for t2 in tickers:
            if t1 == t2:
                row.append(1.0)
            else:
                corr = _correlation(returns_map[t1], returns_map[t2])
                row.append(round(corr, 3) if corr is not None else None)
        matrix.append(row)

    # 이름 단축 (KRW-BTC → BTC)
    short_tickers = [t.replace("KRW-", "") for t in tickers]
    return {"tickers": short_tickers, "matrix": matrix}


# ── 통계 유틸 ────────────────────────────────────────────────────────────────

def _mean(data: List[float]) -> float:
    return sum(data) / len(data) if data else 0.0


def _variance(data: List[float]) -> float:
    if len(data) < 2:
        return 0.0
    m = _mean(data)
    return sum((x - m) ** 2 for x in data) / (len(data) - 1)


def _covariance(x: List[float], y: List[float]) -> float:
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    mx, my = _mean(x), _mean(y)
    return sum((x[i] - mx) * (y[i] - my) for i in range(len(x))) / (len(x) - 1)


def _correlation(x: List[float], y: List[float]) -> Optional[float]:
    cov = _covariance(x, y)
    std_x = math.sqrt(_variance(x))
    std_y = math.sqrt(_variance(y))
    if std_x == 0 or std_y == 0:
        return None
    return cov / (std_x * std_y)
