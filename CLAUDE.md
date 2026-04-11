# CLAUDE.md

## 프로젝트 개요

키움증권 & 업비트 통합 포트폴리오 웹사이트.
주식(키움증권) + 암호화폐(업비트) 자산을 하나의 대시보드에서 조회·관리한다.

## 기술 스택

- **백엔드**: Python + FastAPI + SQLAlchemy (SQLite)
- **프론트엔드**: 바닐라 HTML/CSS/JS (Next.js 전환 예정)
- **스케줄러**: APScheduler (1시간 간격 자동 동기화)
- **터널**: ngrok (외부 접근용)

## 디렉토리 구조

```
stock-portfolio-website/
├── backend/
│   ├── main.py          # FastAPI 앱 진입점, 라우터 등록, 정적 파일 서빙
│   ├── database.py      # SQLAlchemy 모델 (PortfolioSnapshot, AssetSnapshot, NewsReport, PriceAlert)
│   ├── scheduler.py     # APScheduler 기반 포트폴리오 동기화 + 메모리 캐시
│   ├── routers/
│   │   ├── auth.py      # JWT 인증 (/auth/token)
│   │   └── portfolio.py # 포트폴리오 API (/api/*)
│   └── services/
│       └── upbit.py     # 업비트 REST API 연동
├── frontend/
│   ├── index.html       # 메인 대시보드
│   └── login.html       # 로그인 페이지
├── docs/
│   └── requirements/
│       └── phase1-portfolio.md  # Phase 1 상세 요구사항
└── manage_server.sh     # 서버 시작/중지/상태 관리 스크립트
```

## 서버 관리

```bash
./manage_server.sh install       # 의존성 설치 (최초 1회)
./manage_server.sh start         # 백엔드 + ngrok 터널 시작
./manage_server.sh stop          # 전체 중지
./manage_server.sh status        # 상태 확인
./manage_server.sh sync          # 포트폴리오 수동 동기화
./manage_server.sh logs          # 최근 로그 확인
```

백엔드 서버: `http://localhost:8000`

## API 구조

- `POST /auth/token` — 로그인 (JWT 발급), 인증 불필요
- `GET /api/portfolio` — 현재 포트폴리오 조회 (JWT 필요)
- `POST /api/sync` — 수동 동기화 트리거 (JWT 필요)
- `GET /health` — 헬스체크

## DB 모델

| 모델 | 설명 |
|------|------|
| `PortfolioSnapshot` | 동기화 시점의 전체 포트폴리오 요약 |
| `AssetSnapshot` | 개별 자산 스냅샷 (PortfolioSnapshot에 속함) |
| `NewsReport` | 뉴스 리포트 |
| `PriceAlert` | 가격 알림 설정 |

## 개발 현황 (Phase)

- **Phase 1**: 포트폴리오 통계 및 데이터 분석
  - 대시보드 요약 카드, 보유현황 테이블, 수익률 분석, 자산배분 분석, 리스크 지표
  - 상세 요구사항: `docs/requirements/phase1-portfolio.md`

## 주요 환경 변수 (.env)

`backend/.env` 파일에 설정:
- `NGROK_AUTHTOKEN` — ngrok 인증 토큰
- 업비트 API 키 관련 변수 (`services/upbit.py` 참고)
