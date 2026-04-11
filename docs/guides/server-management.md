# 서버 관리 가이드

> 대상: 서버 운영자 (맥북 로컬 환경 기준)

---

## 전제 조건

| 항목 | 내용 |
|------|------|
| Python | 3.9 이상 |
| 프로젝트 루트 | `stock-portfolio-website/` |
| 환경변수 파일 | `backend/.env` |
| 관리 스크립트 | `./manage_server.sh` (프로젝트 루트에서 실행) |

---

## 최초 설치 (최초 1회)

```bash
cd stock-portfolio-website
./manage_server.sh install
```

Python 가상환경 생성 및 의존성 패키지를 자동 설치합니다.

---

## 환경변수 설정 (`backend/.env`)

```env
# 업비트 API 키 (upbit.com → 마이페이지 → Open API 관리)
UPBIT_ACCESS_KEY=발급받은_액세스키
UPBIT_SECRET_KEY=발급받은_시크릿키

# 앱 로그인 계정
APP_USERNAME=아이디
APP_PASSWORD=비밀번호

# JWT 서명 키 (임의의 긴 문자열로 변경 권장)
JWT_SECRET_KEY=랜덤하고_긴_문자열

# ngrok 인증 토큰 (dashboard.ngrok.com/get-started/your-authtoken)
NGROK_AUTHTOKEN=ngrok_토큰
```

> `.env` 파일을 수정한 뒤에는 **서버를 재시작**해야 반영됩니다.

---

## 서버 시작 / 중단

### 전체 시작 (백엔드 + ngrok 터널)

```bash
./manage_server.sh start
```

- 백엔드 FastAPI 서버를 포트 `8000`에서 실행
- ngrok 터널을 통해 외부 접속 URL 생성

### 백엔드만 시작 (로컬 테스트용)

```bash
./manage_server.sh start-backend
```

### 전체 종료

```bash
./manage_server.sh stop
```

### 재시작

```bash
./manage_server.sh restart
```

---

## 상태 확인

```bash
./manage_server.sh status
```

출력 예시:
```
Backend is running. PID=12345
URL: http://127.0.0.1:8000
Tunnel is running. PID=12346
```

---

## 외부 접속 URL 확인 (핸드폰 접속용)

```bash
./manage_server.sh tunnel-status
```

출력 예시:
```
https://xxxx-xxxx.ngrok-free.app
```

> 무료 ngrok 플랜은 서버 재시작마다 URL이 변경됩니다.  
> 고정 URL이 필요하면 **Cloudflare Tunnel** 전환을 권장합니다 (무료, 설정 필요).

---

## 포트폴리오 수동 동기화

업비트 데이터를 즉시 갱신하려면:

```bash
./manage_server.sh sync
```

> 자동 동기화는 1시간 간격으로 백그라운드에서 실행됩니다.

---

## 로그 확인

```bash
./manage_server.sh logs
```

실시간 로그 스트리밍:

```bash
tail -f backend/server.log
```

---

## 전체 명령어 목록

| 명령어 | 설명 |
|--------|------|
| `./manage_server.sh install` | 가상환경 생성 + 패키지 설치 |
| `./manage_server.sh start` | 백엔드 + ngrok 전체 시작 |
| `./manage_server.sh stop` | 전체 종료 |
| `./manage_server.sh restart` | 전체 재시작 |
| `./manage_server.sh status` | 실행 상태 확인 |
| `./manage_server.sh start-backend` | 백엔드만 시작 |
| `./manage_server.sh stop-backend` | 백엔드만 종료 |
| `./manage_server.sh tunnel-start` | ngrok 터널만 시작 |
| `./manage_server.sh tunnel-stop` | ngrok 터널만 종료 |
| `./manage_server.sh tunnel-status` | 외부 접속 URL 출력 |
| `./manage_server.sh sync` | 포트폴리오 수동 동기화 |
| `./manage_server.sh logs` | 최근 로그 30줄 출력 |

---

## 트러블슈팅

### 서버 시작 시 `address already in use`

포트 8000이 이미 사용 중입니다. 점유 프로세스를 종료하세요:

```bash
lsof -i :8000
kill <PID>
```

### 업비트 API 401 Unauthorized

1. `backend/.env`의 키가 올바른지 확인
2. 업비트 마이페이지 → Open API 관리에서 **허용 IP** 확인
   - IP 제한이 설정된 경우 현재 서버 IP를 추가하거나 제한 해제

### ngrok 터널 URL 확인이 안 될 때

```bash
curl http://127.0.0.1:4040/api/tunnels
```

ngrok 대시보드가 4040 포트에서 실행 중이어야 합니다.

---

## 데이터베이스 위치

```
backend/portfolio.db   ← SQLite 파일 (포트폴리오 이력 저장)
```

백업이 필요하면 이 파일을 복사해두면 됩니다.
