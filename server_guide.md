# Server Management Guide

## 목차
1. 개요
2. 준비하기
3. 설치하기
4. 서버 시작하기
5. 서버 중지하기
6. 상태 확인하기
7. 같은 네트워크에서 접속하기
8. 다른 네트워크에서 접속하기
9. 추가 명령
10. 참고

## 1. 개요
이 문서는 `stock-portfolio-website`의 백엔드와 프론트엔드 실행, 중지, 상태 확인, 원격 접속 방법을 간단하게 정리합니다.

## 2. 준비하기
- Python 3.10 이상 필요
- `backend/.env`에 다음 값을 설정
  - `UPBIT_ACCESS_KEY`
  - `UPBIT_SECRET_KEY`
  - `APP_USERNAME`
  - `APP_PASSWORD`
  - `NGROK_AUTHTOKEN` (외부 네트워크 접속용 ngrok auth token, 선택 사항)
- `backend/requirements.txt`에 패키지 정의

## 3. 설치하기
```bash
cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website
chmod +x manage_server.sh
./manage_server.sh install
```
- `backend/venv` 생성
- Python 패키지 설치

## 4. 서버 시작하기
```bash
./manage_server.sh start
```
- 백엔드: `http://127.0.0.1:8000`
- 프론트엔드: `http://127.0.0.1:8001`
- PID 파일
  - `backend/uvicorn.pid`
  - `frontend.pid`
- ngrok이 있으면 자동으로 터널도 실행됩니다.

## 5. 서버 중지하기
```bash
./manage_server.sh stop
```
- 백엔드와 프론트엔드를 모두 중지합니다.

## 6. 상태 확인하기
```bash
./manage_server.sh status
```
- 백엔드와 프론트엔드 실행 여부 확인

```bash
./manage_server.sh status-backend
./manage_server.sh status-frontend
```
- 개별 상태 확인

## 7. 같은 네트워크에서 접속하기
1. `./manage_server.sh start`
2. Mac 로컬 IP 확인
   - `ipconfig getifaddr en0`
3. 브라우저에서 접속
   - `http://<Mac_IP>:8001`
4. 인증
   - 사용자 이름: `APP_USERNAME`
   - 비밀번호: `APP_PASSWORD`

예: `http://192.168.45.223:8001`

## 8. 다른 네트워크에서 접속하기
### 8.1 자동 ngrok 터널
`./manage_server.sh start` 실행 시 ngrok이 설치되어 있으면 자동으로 공개 URL을 만듭니다.

```bash
./manage_server.sh tunnel-status
```
- 공개 URL 확인 후 iPhone 등 외부 기기에서 접속

### 8.2 수동 ngrok 터널
```bash
./manage_server.sh start
./manage_server.sh tunnel-start
./manage_server.sh tunnel-status
```
- 프론트엔드 포트 `8001`을 인터넷에 노출
- ngrok이 프로젝트 루트에 포함되어 있으므로 별도 설치가 필요하지 않습니다.

## 9. 추가 명령
- 강제 동기화
  ```bash
  ./manage_server.sh sync
  ```
- 포트폴리오 데이터 확인
  ```bash
  ./manage_server.sh portfolio
  ```
- 로그 확인
  ```bash
  ./manage_server.sh logs
  ```
- 프론트엔드만 실행
  ```bash
  ./manage_server.sh start-frontend
  ```
- 프론트엔드만 중지
  ```bash
  ./manage_server.sh stop-frontend
  ```

## 10. 참고
- `manage_server.sh`는 프로젝트 루트에서 실행
- 백엔드가 실행되어야 프론트엔드가 API 데이터를 정상적으로 가져옵니다
- `backend/.env`에 API 키가 없으면 Upbit 데이터가 작동하지 않습니다
