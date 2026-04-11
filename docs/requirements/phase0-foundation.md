# Phase 0: 기반 정비

## 0-1. 인증 방식 개선 — HTTP Basic → JWT 로그인 페이지

- 현재 Basic Auth는 브라우저 팝업으로 모바일 UX가 나쁨
- `/login` HTML 페이지에서 아이디·비밀번호 입력 → JWT 토큰 발급
- 프론트엔드는 `localStorage`에 JWT 저장, 모든 API 요청에 Bearer 헤더 첨부
- 토큰 만료 시 자동으로 로그인 페이지로 리다이렉트

## 0-2. SQLite 데이터베이스 도입

- `SQLAlchemy` + `aiosqlite` 사용
- 테이블 구조:

```
portfolio_snapshots  # 시간별 포트폴리오 스냅샷 (이력 차트용)
  id, timestamp, total_value, total_profit_loss, total_profit_loss_rate

assets               # 개별 자산 스냅샷
  id, snapshot_id, name, ticker, quantity, avg_price, current_price,
  total_value, profit_loss, profit_loss_rate, asset_type

news_reports         # 수집된 뉴스 캐시
  id, created_at, category, title, summary, source, url

price_alerts         # 가격 알림 설정 (Phase 4)
  id, ticker, condition, threshold, is_active
```

## 0-3. Cloudflare Tunnel 설정 (ngrok 대체)

- 무료, 고정 URL, 인증 없이도 HTTPS 지원
- `cloudflared tunnel` 바이너리 설치 후 `manage_server.sh`에 통합
- ngrok은 URL이 매번 바뀌어 핸드폰 북마크 불가 → Cloudflare로 해결

## 0-4. 프로젝트 구조 정리

- routers/, services/ 디렉토리 분리
- 각 기능별 모듈화 (auth, portfolio, analytics, news)
