"""유동성 흐름 서비스 — FRED / Yahoo Finance / CoinGecko 데이터 수집 + 코멘트 생성."""
import logging
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import requests
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

FRED_API_KEY = os.getenv("FRED_API_KEY", "")

# ── FRED API ──────────────────────────────────────────────────────────────────

def _fred_series(series_id: str, days: int = 365) -> List[Dict[str, Any]]:
    """FRED 시계열 데이터를 조회한다."""
    if not FRED_API_KEY:
        return []
    start = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    try:
        res = requests.get(
            "https://api.stlouisfed.org/fred/series/observations",
            params={
                "series_id": series_id,
                "api_key": FRED_API_KEY,
                "file_type": "json",
                "observation_start": start,
                "sort_order": "asc",
            },
            timeout=15,
        )
        res.raise_for_status()
        obs = res.json().get("observations", [])
        return [
            {"date": o["date"], "value": float(o["value"])}
            for o in obs
            if o["value"] != "."
        ]
    except Exception as e:
        logger.error(f"FRED {series_id} 조회 실패: {e}")
        return []


# ── Yahoo Finance ─────────────────────────────────────────────────────────────

def _yahoo_history(ticker: str, days: int = 365) -> List[Dict[str, Any]]:
    """Yahoo Finance에서 종가 시계열을 가져온다."""
    try:
        import yfinance as yf
        end = datetime.now()
        start = end - timedelta(days=days)
        df = yf.download(ticker, start=start.strftime("%Y-%m-%d"), end=end.strftime("%Y-%m-%d"), progress=False)
        if df.empty:
            return []
        result = []
        for date, row in df.iterrows():
            close = row["Close"]
            # yfinance may return Series or scalar
            val = float(close.iloc[0]) if hasattr(close, 'iloc') else float(close)
            result.append({"date": date.strftime("%Y-%m-%d"), "value": val})
        return result
    except Exception as e:
        logger.error(f"Yahoo {ticker} 조회 실패: {e}")
        return []


# ── CoinGecko ─────────────────────────────────────────────────────────────────

def _crypto_proxy(days: int = 365) -> List[Dict[str, Any]]:
    """BTC 가격을 크립토 시장 대리지표로 사용한다 (Yahoo Finance)."""
    return _yahoo_history("BTC-USD", days)


# ── 데이터 수집 통합 ──────────────────────────────────────────────────────────

def _normalize_monthly(series: List[Dict]) -> List[Dict]:
    """일별 데이터를 월말 기준으로 리샘플링한다."""
    if not series:
        return []
    monthly = {}
    for item in series:
        key = item["date"][:7]  # YYYY-MM
        monthly[key] = item  # 마지막 값이 남음
    return [{"date": k, "value": v["value"]} for k, v in sorted(monthly.items())]


def _normalize_weekly(series: List[Dict]) -> List[Dict]:
    """일별 데이터를 주간(금요일 기준)으로 리샘플링한다."""
    if not series:
        return []
    from datetime import date as dt_date
    weekly = {}
    for item in series:
        d = datetime.strptime(item["date"][:10], "%Y-%m-%d")
        # ISO 주차 기준 (YYYY-WNN)
        iso = d.isocalendar()
        key = f"{iso[0]}-W{iso[1]:02d}"
        weekly[key] = item  # 해당 주의 마지막 값
    return [{"date": k, "value": v["value"]} for k, v in sorted(weekly.items())]


def get_liquidity_flow(days: int = 365) -> Dict[str, Any]:
    """유동성 흐름 데이터를 수집하고 코멘트를 생성한다."""
    logger.info(f"유동성 흐름 데이터 수집 시작 (days={days})")

    # 데이터 수집
    raw = {
        # 자산군
        "m2": _fred_series("WM2NS", days),           # 미국 M2 (주간, 10억달러)
        "mmf": _fred_series("MMMFFAQ027S", days),     # MMF 총자산 (분기)
        "stocks": _yahoo_history("SPY", days),         # S&P500 ETF
        "bonds": _yahoo_history("TLT", days),          # 장기국채 ETF
        "gold": _yahoo_history("GLD", days),            # 금 ETF
        "commodities": _yahoo_history("DBC", days),     # 원자재 ETF
        "crypto": _crypto_proxy(days),                    # BTC 가격 (크립토 대리지표)
        # 선행지표
        "dxy": _yahoo_history("DX-Y.NYB", days),       # 달러 인덱스
        "vix": _yahoo_history("^VIX", days),            # 공포지수
        "yield_spread": _fred_series("T10Y2Y", days),   # 10년-2년 금리차
    }

    # 주간 리샘플링
    weekly = {}
    for key, series in raw.items():
        weekly[key] = _normalize_weekly(series)

    # 하위 호환: monthly 키도 유지
    monthly = weekly

    # 최신 값과 변화율 계산
    current = {}
    for key, series in monthly.items():
        if len(series) >= 2:
            latest = series[-1]["value"]
            prev = series[-2]["value"]
            change = (latest - prev) / prev * 100 if prev != 0 else 0
            current[key] = {
                "value": round(latest, 2),
                "prev_value": round(prev, 2),
                "change_pct": round(change, 2),
                "direction": "up" if change > 0 else "down" if change < 0 else "flat",
            }
        elif len(series) == 1:
            current[key] = {
                "value": round(series[-1]["value"], 2),
                "prev_value": None,
                "change_pct": 0,
                "direction": "flat",
            }
        else:
            current[key] = {"value": None, "prev_value": None, "change_pct": 0, "direction": "flat"}

    # 코멘트 생성
    comments = _generate_comments(current)

    # 산키 데이터 생성
    sankey = _build_sankey(current)

    return {
        "current": current,
        "monthly": {k: v for k, v in monthly.items()},
        "comments": comments,
        "sankey": sankey,
        "updated_at": datetime.now().isoformat(),
    }


# ── 코멘트 자동 생성 ─────────────────────────────────────────────────────────

ASSET_LABELS = {
    "m2": "글로벌 M2",
    "stocks": "미국 주식",
    "bonds": "채권",
    "mmf": "현금성(MMF)",
    "gold": "금",
    "crypto": "코인",
    "commodities": "원자재",
    "dxy": "달러(DXY)",
    "vix": "공포지수(VIX)",
    "yield_spread": "장단기 금리차",
}


def _generate_comments(current: Dict) -> Dict[str, Any]:
    """각 자산군 변화에 따른 코멘트를 자동 생성한다."""
    per_asset = {}

    # M2
    m2 = current.get("m2", {})
    if m2.get("change_pct", 0) > 1:
        per_asset["m2"] = "유동성 확장 중. 시중에 돈이 늘고 있어 자산 가격에 긍정적."
    elif m2.get("change_pct", 0) < -1:
        per_asset["m2"] = "유동성 긴축 중. 시중의 돈이 줄고 있어 자산 가격에 부정적."
    else:
        per_asset["m2"] = "유동성 변화 미미. 큰 방향성 없음."

    # 주식
    stocks = current.get("stocks", {})
    chg = stocks.get("change_pct", 0)
    if chg > 3:
        per_asset["stocks"] = "강한 매수세. 위험자산 선호 심리 확대."
    elif chg < -3:
        per_asset["stocks"] = "자금 유출. 투자 심리 위축, 안전자산 선호 가능성."
    else:
        per_asset["stocks"] = "횡보 중. 뚜렷한 방향성 없음."

    # 채권
    bonds = current.get("bonds", {})
    chg = bonds.get("change_pct", 0)
    if chg > 2:
        per_asset["bonds"] = "채권 유입 증가. 금리 인하 기대 또는 안전자산 도피."
    elif chg < -2:
        per_asset["bonds"] = "채권에서 자금 유출. 금리 상승 우려 또는 위험자산 선호."
    else:
        per_asset["bonds"] = "안정적 유지."

    # 현금성 (MMF)
    mmf = current.get("mmf", {})
    chg = mmf.get("change_pct", 0)
    if chg > 2:
        per_asset["mmf"] = "현금 비축 증가. 극도의 관망세. 하지만 미래 상승의 연료가 될 수 있음."
    elif chg < -2:
        per_asset["mmf"] = "대기 자금이 시장으로 유입 중. 리스크 온 신호."
    else:
        per_asset["mmf"] = "대기 자금 변화 미미."

    # 금
    gold = current.get("gold", {})
    chg = gold.get("change_pct", 0)
    if chg > 3:
        per_asset["gold"] = "안전자산 랠리. 불확실성에 자금이 금으로 이동 중."
    elif chg < -3:
        per_asset["gold"] = "금에서 자금 유출. 위험자산 선호 전환 신호."
    else:
        per_asset["gold"] = "안정적 흐름."

    # 코인
    crypto = current.get("crypto", {})
    chg = crypto.get("change_pct", 0)
    if chg > 5:
        per_asset["crypto"] = "강한 유입. 유동성 확장에 코인이 선반영 중."
    elif chg < -5:
        per_asset["crypto"] = "대규모 자금 유출. 위험자산 회피 심화."
    else:
        per_asset["crypto"] = "코인 시장 변동 제한적."

    # 원자재
    comm = current.get("commodities", {})
    chg = comm.get("change_pct", 0)
    if chg > 3:
        per_asset["commodities"] = "원자재 수요 증가. 인플레이션 헤지 또는 경기 회복 신호."
    elif chg < -3:
        per_asset["commodities"] = "원자재 수요 감소. 경기 둔화 우려."
    else:
        per_asset["commodities"] = "혼조세."

    # ── 선행지표 ──

    # DXY (달러 인덱스)
    dxy = current.get("dxy", {})
    chg = dxy.get("change_pct", 0)
    if chg > 1.5:
        per_asset["dxy"] = "⚠️ 달러 강세. 신흥국·코인·원자재에 하방 압력. 위험자산 약세 예고."
    elif chg < -1.5:
        per_asset["dxy"] = "🟢 달러 약세 전환. 위험자산(주식/코인)으로 자금 이동 예상."
    else:
        per_asset["dxy"] = "달러 횡보. 방향성 제한적."

    # VIX (공포지수)
    vix = current.get("vix", {})
    vix_val = vix.get("value", 0) or 0
    if vix_val > 35:
        per_asset["vix"] = "🔴 극도의 공포. 패닉셀 진행 중. 역설적 매수 기회 탐색 구간."
    elif vix_val > 25:
        per_asset["vix"] = "⚠️ 불안 확대. 안전자산 이동 가속. 주식/코인 추가 하락 가능."
    elif vix_val < 15:
        per_asset["vix"] = "과도한 낙관. 변동성 확대 전 잠잠한 구간일 수 있음."
    else:
        per_asset["vix"] = "정상 범위. 시장 안정적."

    # 장단기 금리차
    ys = current.get("yield_spread", {})
    ys_val = ys.get("value", 0) or 0
    if ys_val < 0:
        per_asset["yield_spread"] = "🔴 수익률 곡선 역전. 경기 침체 경고 신호 (2~6개월 선행)."
    elif ys_val < 0.3:
        per_asset["yield_spread"] = "⚠️ 금리차 축소. 경기 둔화 초기 신호."
    elif ys_val > 1.0:
        per_asset["yield_spread"] = "🟢 정상적 금리 구조. 경기 확장 환경."
    else:
        per_asset["yield_spread"] = "금리차 정상 범위."

    # 종합 해석
    summary = _generate_summary(current)

    return {
        "per_asset": per_asset,
        "summary": summary,
    }


def _generate_summary(current: Dict) -> str:
    """종합 해석을 생성한다."""
    signals = []

    m2_chg = current.get("m2", {}).get("change_pct", 0)
    stocks_chg = current.get("stocks", {}).get("change_pct", 0)
    mmf_chg = current.get("mmf", {}).get("change_pct", 0)
    gold_chg = current.get("gold", {}).get("change_pct", 0)
    crypto_chg = current.get("crypto", {}).get("change_pct", 0)

    # 리스크 온/오프 판단
    if stocks_chg < -3 and (gold_chg > 2 or mmf_chg > 2):
        signals.append("리스크 오프: 주식에서 빠진 돈이 안전자산(금/현금)으로 이동 중.")
    elif stocks_chg > 3 and mmf_chg < -1:
        signals.append("리스크 온: 대기 자금이 주식 시장으로 유입 중.")

    # M2 확장 + 코인
    if m2_chg > 1 and crypto_chg > 3:
        signals.append("M2 확장에 코인이 선반영. 유동성 장세 가능성.")

    # MMF 역대급
    if current.get("mmf", {}).get("value", 0) and mmf_chg > 0:
        signals.append("MMF 잔고 증가 중. 아직 투자되지 않은 대기 자금이 풍부.")

    # M2 감소 경고
    if m2_chg < -1:
        signals.append("⚠️ M2 감소 중. 유동성 긴축 환경에서 자산 가격 하방 압력.")

    # 선행지표 시그널
    dxy_chg = current.get("dxy", {}).get("change_pct", 0)
    vix_val = current.get("vix", {}).get("value", 0) or 0
    ys_val = current.get("yield_spread", {}).get("value", 0) or 0

    if dxy_chg < -1.5 and m2_chg > 0:
        signals.append("🟢 달러 약세 + M2 확장 = 불장 환경 조성 중.")
    elif dxy_chg > 1.5 and vix_val > 25:
        signals.append("🔴 달러 강세 + 공포 확대 = 위험자산 추가 하락 경계.")

    if vix_val > 35:
        signals.append("극단적 공포 구간. 역사적으로 중장기 매수 기회였던 구간.")

    if ys_val < 0:
        signals.append("⚠️ 수익률 곡선 역전 중. 경기 침체 가능성 주시 필요.")

    if not signals:
        signals.append("뚜렷한 유동성 방향 신호 없음. 관망 유지.")

    return " ".join(signals)


# ── 산키 다이어그램 데이터 ────────────────────────────────────────────────────

def _build_sankey(current: Dict) -> Dict[str, Any]:
    """산키 다이어그램용 노드 + 링크 데이터를 생성한다."""
    destinations = ["stocks", "bonds", "mmf", "gold", "crypto", "commodities"]

    nodes = [{"name": "M2 공급"}]
    for key in destinations:
        nodes.append({"name": ASSET_LABELS.get(key, key)})

    links = []
    for i, key in enumerate(destinations):
        chg = abs(current.get(key, {}).get("change_pct", 0))
        # 변화율을 흐름 굵기로 (최소 1)
        value = max(chg, 1)
        direction = current.get(key, {}).get("direction", "flat")
        links.append({
            "source": 0,
            "target": i + 1,
            "value": round(value, 1),
            "direction": direction,
        })

    return {"nodes": nodes, "links": links}
