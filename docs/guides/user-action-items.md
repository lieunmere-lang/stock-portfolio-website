# 사용자 액션 아이템

## 🔒 보안 (우선순위 높음)

- [ ] `.env`에 강한 JWT 시크릿 키 설정
  ```
  JWT_SECRET_KEY=여기에_64자_이상_랜덤_문자열
  ```
  생성 방법: `python3 -c "import secrets; print(secrets.token_hex(32))"`

- [ ] GitHub에 .env가 이전 커밋에 올라갔는지 확인
  - 올라갔다면 아래 API 키 전부 재발급:
    - Upbit API 키
    - Kiwoom API 키
    - Anthropic API 키
    - Alpha Vantage API 키
    - FRED API 키
    - ngrok 토큰

## 🤖 디스코드 금융봇 설정

- [ ] Discord Developer Portal에서 봇 생성
  - https://discord.com/developers/applications
  - New Application → 이름 지정 → Bot 탭 → Add Bot
  - TOKEN 복사
  - Message Content Intent 활성화

- [ ] `.env`에 봇 토큰 설정
  ```
  DISCORD_BOT_TOKEN=복사한_토큰
  DISCORD_GUILD_ID=서버_ID
  ```

- [ ] 봇을 서버에 초대
  - OAuth2 → URL Generator
  - Scopes: `bot`, `applications.commands`
  - Permissions: `Send Messages`, `Embed Links`, `Read Message History`
  - 생성된 URL로 서버에 초대

- [ ] 디스코드 서버에 채널 만들기
  ```
  📈 금융 (카테고리)
    #뉴스리포트
    #가격알림
    #시장지표
  ```

- [ ] 채널 설정 스크립트 실행
  ```bash
  cd backend && python3 setup_bot.py
  ```

- [ ] 서버 시작 및 봇 동작 확인
  ```bash
  ./manage_server.sh start
  ```
  - 봇 온라인 확인
  - `/리포트`, `/지표` 명령어 테스트

## 상세 가이드

- 디스코드 봇 설정: `docs/guides/discord-bot-setup.md`
