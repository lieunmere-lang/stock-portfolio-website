from fastapi import APIRouter, Depends, Request

from routers.auth import verify_token

router = APIRouter(prefix="/api/news")


def require_auth(request: Request) -> str:
    from fastapi import HTTPException, status

    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="인증이 필요합니다.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = auth_header.removeprefix("Bearer ").strip()
    return verify_token(token)


MOCK_REPORT = {
    "report_date": "2026-04-12",
    "created_at": "2026-04-12T09:00:00",
    "model_used": "claude-haiku-4-5",
    "total_collected": 287,
    "total_selected": 12,
    "summary": (
        "미 연준이 금리 동결을 시사하며 글로벌 증시가 상승세를 보이고 있습니다. "
        "미·중 무역협상 재개 기대감과 함께 기술주 중심으로 매수세가 유입됐으며, "
        "비트코인 ETF로의 자금 유입이 지속되면서 암호화폐 시장도 강세를 유지하고 있습니다. "
        "RKLB는 NASA 계약 수주 소식으로 급등했고, TSLA는 FSD 규제 승인 기대로 반등했습니다."
    ),
    "market_indicators": {
        "fear_greed": {"value": 72, "label": "탐욕"},
        "btc_dominance": 52.3,
        "vix": 14.2,
    },
    "items": [
        {
            "id": 1,
            "category": "macro",
            "title": "파월 의장, 금리 동결 시사 — '데이터 의존적' 기조 재확인",
            "summary": (
                "제롬 파월 연준 의장이 4월 FOMC 의사록 공개 전 발언에서 "
                "현재 금리 수준이 적절하다고 언급하며 추가 인상 가능성을 일축했습니다. "
                "시장은 6월 첫 인하 가능성을 65%로 반영하고 있습니다."
            ),
            "impact_analysis": (
                "금리 동결 기조는 성장주 전반에 긍정적입니다. "
                "보유 중인 TSLA, RKLB 등 고베타 기술주에 우호적인 환경이 지속될 것으로 보입니다."
            ),
            "related_ticker": "TSLA",
            "source": "Reuters",
            "source_url": "https://reuters.com/example/fed-powell-rate-hold",
            "importance": 5,
        },
        {
            "id": 2,
            "category": "macro",
            "title": "미·중 무역협상 재개 — 반도체·AI 분야 관세 완화 논의",
            "summary": (
                "미국과 중국이 스위스 제네바에서 고위급 무역협상을 재개했습니다. "
                "반도체 장비 수출 규제 완화와 상호 관세 인하가 주요 의제로, "
                "협상이 타결될 경우 글로벌 공급망 리스크가 크게 줄어들 전망입니다."
            ),
            "impact_analysis": None,
            "related_ticker": None,
            "source": "Bloomberg",
            "source_url": "https://bloomberg.com/example/us-china-trade",
            "importance": 4,
        },
        {
            "id": 3,
            "category": "macro",
            "title": "유로존 3월 PMI 54.2 — 제조업 회복세 뚜렷",
            "summary": (
                "유로존 3월 합성 PMI가 54.2로 집계돼 22개월 만에 최고치를 기록했습니다. "
                "독일 제조업 PMI도 51.8로 확장 국면을 회복하며 유럽 경기 회복 기대가 높아지고 있습니다."
            ),
            "impact_analysis": None,
            "related_ticker": None,
            "source": "S&P Global",
            "source_url": "https://spglobal.com/example/eurozone-pmi",
            "importance": 3,
        },
        {
            "id": 4,
            "category": "macro",
            "title": "이번 주 주요 경제 지표 캘린더 — CPI·소매판매·실업수당 청구",
            "summary": (
                "4월 셋째 주에는 미국 3월 CPI(화), 소매판매(수), 주간 실업수당 청구(목)가 예정돼 있습니다. "
                "CPI 컨센서스는 전년비 3.1%로 전월(3.2%)보다 소폭 하락 예상입니다."
            ),
            "impact_analysis": None,
            "related_ticker": None,
            "source": "MarketWatch",
            "source_url": "https://marketwatch.com/example/economic-calendar",
            "importance": 3,
        },
        {
            "id": 5,
            "category": "stock",
            "title": "RKLB, NASA 달 탐사 발사 계약 4억 달러 수주",
            "summary": (
                "Rocket Lab(RKLB)이 NASA의 달 탐사 미션용 Neutron 로켓 발사 서비스 계약을 "
                "4억 달러 규모로 수주했다고 발표했습니다. "
                "계약은 2027~2029년 3회 발사를 포함하며, SpaceX와의 경쟁에서 처음으로 대형 계약을 따낸 사례입니다."
            ),
            "impact_analysis": (
                "보유 중인 RKLB에 매우 긍정적입니다. "
                "대형 정부 계약 수주로 수익 가시성이 크게 높아졌으며 목표주가 상향 조정이 기대됩니다."
            ),
            "related_ticker": "RKLB",
            "source": "Space News",
            "source_url": "https://spacenews.com/example/rklb-nasa-contract",
            "importance": 5,
        },
        {
            "id": 6,
            "category": "stock",
            "title": "TSLA, FSD v13 중국 규제 승인 임박 — 현지 출시 기대",
            "summary": (
                "테슬라 FSD(Full Self-Driving) v13이 중국 공업정보화부(MIIT)의 최종 심사 단계에 있으며 "
                "이르면 4월 말 출시가 가능하다는 소식이 전해졌습니다. "
                "중국은 테슬라 전체 매출의 약 22%를 차지하는 핵심 시장입니다."
            ),
            "impact_analysis": (
                "보유 중인 TSLA에 긍정적입니다. "
                "중국 FSD 출시는 소프트웨어 수익 확대로 이어지며 마진 개선에 기여할 것으로 보입니다."
            ),
            "related_ticker": "TSLA",
            "source": "The Information",
            "source_url": "https://theinformation.com/example/tesla-fsd-china",
            "importance": 4,
        },
        {
            "id": 7,
            "category": "stock",
            "title": "CRCL(Circle Internet), 나스닥 상장 신청 공식 제출 — 기업가치 80억 달러 목표",
            "summary": (
                "USDC 발행사 Circle Internet이 S-1 서류를 SEC에 제출하며 나스닥 상장을 공식화했습니다. "
                "예상 공모가 기준 기업가치는 약 80억 달러이며, 스테이블코인 규제 명확화 시 수혜가 예상됩니다."
            ),
            "impact_analysis": (
                "보유 중인 CRCL의 IPO 상장이 확정됨에 따라 공모가 기준 평가 가능해졌습니다. "
                "스테이블코인 법안 통과 여부가 단기 주가의 핵심 변수입니다."
            ),
            "related_ticker": "CRCL",
            "source": "SEC EDGAR",
            "source_url": "https://sec.gov/example/circle-s1",
            "importance": 4,
        },
        {
            "id": 8,
            "category": "crypto",
            "title": "비트코인 현물 ETF, 주간 순유입 22억 달러 — 4주 연속 유입세",
            "summary": (
                "미국 비트코인 현물 ETF(BlackRock IBIT 등)로의 주간 순유입액이 22억 달러를 기록하며 "
                "4주 연속 유입세를 이어갔습니다. "
                "BTC는 9만 2,000달러 선을 회복하며 연고점 경신을 시도하고 있습니다."
            ),
            "impact_analysis": None,
            "related_ticker": None,
            "source": "Farside Investors",
            "source_url": "https://farside.co.uk/example/btc-etf-flows",
            "importance": 4,
        },
        {
            "id": 9,
            "category": "crypto",
            "title": "이더리움 Pectra 업그레이드 5월 7일 확정 — 스테이킹 한도 상향",
            "summary": (
                "이더리움 코어 개발팀이 Pectra 하드포크를 5월 7일 메인넷에 적용한다고 확정했습니다. "
                "검증자 최대 스테이킹 한도가 32 ETH에서 2,048 ETH로 대폭 상향되며 "
                "스테이킹 효율성이 크게 개선될 예정입니다."
            ),
            "impact_analysis": (
                "보유 중인 KRW-ETH2(이더리움 스테이킹 포지션)에 긍정적입니다. "
                "스테이킹 한도 확대로 리스테이킹 프로토콜의 TVL 증가가 기대됩니다."
            ),
            "related_ticker": "KRW-ETH2",
            "source": "Ethereum Blog",
            "source_url": "https://blog.ethereum.org/example/pectra-mainnet",
            "importance": 4,
        },
        {
            "id": 10,
            "category": "sentiment",
            "title": "Reddit r/investing, RKLB 언급량 3배 급증 — 개인 투자자 관심 폭발",
            "summary": (
                "NASA 계약 수주 소식 이후 Reddit r/investing과 r/wallstreetbets에서 "
                "RKLB 언급량이 전주 대비 3배 이상 증가했습니다. "
                "소셜 미디어 센티멘트 분석 플랫폼 Stocktwits에서도 불리시 의견이 87%를 기록했습니다."
            ),
            "impact_analysis": (
                "보유 중인 RKLB에 단기적으로 긍정적인 수급 효과가 예상됩니다. "
                "다만 단기 급등 후 차익 실현 매물이 나올 수 있어 분할 매도 전략을 고려할 필요가 있습니다."
            ),
            "related_ticker": "RKLB",
            "source": "Stocktwits",
            "source_url": "https://stocktwits.com/example/rklb-sentiment",
            "importance": 3,
        },
        {
            "id": 11,
            "category": "sentiment",
            "title": "CNN Fear & Greed 지수 72 '탐욕' — 단기 과열 경고",
            "summary": (
                "CNN Fear & Greed 지수가 72포인트를 기록하며 '탐욕(Greed)' 구간에 진입했습니다. "
                "지수가 75 이상으로 올라설 경우 '극도의 탐욕' 구간으로 분류되며 "
                "과거 데이터상 단기 조정이 발생할 확률이 높아지는 경향이 있습니다."
            ),
            "impact_analysis": None,
            "related_ticker": None,
            "source": "CNN Business",
            "source_url": "https://money.cnn.com/data/fear-and-greed",
            "importance": 2,
        },
        {
            "id": 12,
            "category": "hiring",
            "title": "Palantir, AI 플랫폼 엔지니어 300명 채용 공고 — TEM 간접 수혜 가능성",
            "summary": (
                "Palantir Technologies가 AIP(AI Platform) 확장을 위해 소프트웨어 엔지니어 300명을 "
                "신규 채용한다고 발표했습니다. "
                "헬스케어 AI 분야 인력 수요도 포함되어 있어 의료 AI 솔루션 기업들의 경쟁 심화가 예상됩니다."
            ),
            "impact_analysis": (
                "보유 중인 TEM(Tempus AI)의 경쟁 환경이 다소 심화될 수 있습니다. "
                "그러나 헬스케어 AI 시장 자체의 성장이 가속화되는 측면에서 간접 수혜도 가능합니다."
            ),
            "related_ticker": "TEM",
            "source": "LinkedIn",
            "source_url": "https://linkedin.com/example/palantir-hiring",
            "importance": 2,
        },
    ],
}

MOCK_REPORTS_LIST = [
    {
        "report_date": "2026-04-12",
        "created_at": "2026-04-12T09:00:00",
        "model_used": "claude-haiku-4-5",
        "total_collected": 287,
        "total_selected": 12,
        "summary_preview": "미 연준이 금리 동결을 시사하며 글로벌 증시가 상승세를 보이고 있습니다...",
    },
    {
        "report_date": "2026-04-11",
        "created_at": "2026-04-11T09:00:00",
        "model_used": "claude-haiku-4-5",
        "total_collected": 263,
        "total_selected": 11,
        "summary_preview": "미국 3월 PPI가 예상치를 하회하며 인플레이션 완화 기대가 높아졌습니다...",
    },
    {
        "report_date": "2026-04-10",
        "created_at": "2026-04-10T09:00:00",
        "model_used": "claude-haiku-4-5",
        "total_collected": 241,
        "total_selected": 10,
        "summary_preview": "FOMC 의사록에서 다수 위원이 연내 금리 인하를 지지한 것으로 나타났습니다...",
    },
    {
        "report_date": "2026-04-09",
        "created_at": "2026-04-09T09:00:00",
        "model_used": "claude-haiku-4-5",
        "total_collected": 198,
        "total_selected": 9,
        "summary_preview": "국제유가가 배럴당 78달러를 돌파하며 에너지 섹터가 강세를 보였습니다...",
    },
    {
        "report_date": "2026-04-08",
        "created_at": "2026-04-08T09:00:00",
        "model_used": "claude-haiku-4-5",
        "total_collected": 215,
        "total_selected": 10,
        "summary_preview": "중동 지정학적 긴장 완화 소식에 위험자산 선호 심리가 강화됐습니다...",
    },
]


@router.get("/latest")
def get_latest_report(user: str = Depends(require_auth)):
    """최신 뉴스 리포트 조회"""
    return MOCK_REPORT


@router.get("/report/{report_date}")
def get_report_by_date(report_date: str, user: str = Depends(require_auth)):
    """특정 날짜 뉴스 리포트 조회"""
    return MOCK_REPORT


@router.get("/reports")
def list_reports(
    offset: int = 0,
    limit: int = 10,
    user: str = Depends(require_auth),
):
    """뉴스 리포트 목록 조회 (페이지네이션)"""
    total = len(MOCK_REPORTS_LIST)
    items = MOCK_REPORTS_LIST[offset : offset + limit]
    return {
        "items": items,
        "total": total,
        "has_more": offset + limit < total,
    }
