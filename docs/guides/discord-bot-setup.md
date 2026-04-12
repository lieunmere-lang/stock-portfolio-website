# Discord 금융봇 설정 가이드

## 1. Discord Developer Portal에서 봇 생성

1. https://discord.com/developers/applications 접속
2. **New Application** 클릭 → 이름: "금융봇" (원하는 이름)
3. 좌측 메뉴 **Bot** 탭 클릭
4. **TOKEN** → **Copy** 클릭 → 토큰 복사해두기
5. 아래쪽 **Privileged Gateway Intents** 섹션에서:
   - **Message Content Intent** → 활성화 (토글 ON)
6. **Save Changes**

## 2. .env에 토큰 설정

`backend/.env` 파일에 복사한 토큰 붙여넣기:

```
DISCORD_BOT_TOKEN=여기에_복사한_토큰_붙여넣기
DISCORD_GUILD_ID=여기에_서버_ID_붙여넣기
```

**서버 ID 확인 방법:**
- 디스코드 앱 → 설정 → 고급 → **개발자 모드** 활성화
- 서버 이름 우클릭 → **ID 복사**

## 3. 봇을 서버에 초대

1. Developer Portal에서 좌측 메뉴 **OAuth2** → **URL Generator**
2. **Scopes** 선택:
   - `bot`
   - `applications.commands`
3. **Bot Permissions** 선택:
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`
4. 하단에 생성된 URL 복사 → 브라우저에서 열기
5. 봇을 초대할 서버 선택 → **승인**

## 4. 디스코드 서버에 채널 만들기

서버에서 다음 구조로 채널 생성:

```
📈 금융 (카테고리)
  #뉴스리포트
  #가격알림
  #시장지표
```

**채널 ID 확인 방법:**
- 채널 이름 우클릭 → **ID 복사** (개발자 모드 필요)

## 5. 채널 설정 스크립트 실행

```bash
cd backend
python3 setup_bot.py
```

각 채널 ID를 입력하면 DB에 설정이 저장됩니다.

## 6. 서버 시작

```bash
./manage_server.sh start
```

디스코드에서 봇이 온라인 상태인지 확인하고, `/리포트`와 `/지표` 명령어를 테스트해보세요.

## 슬래시 명령어 목록

| 명령어 | 설명 | 예시 |
|--------|------|------|
| `/리포트` | 최신 뉴스 리포트 조회 | `/리포트` |
| `/지표` | 현재 시장 지표 조회 | `/지표` |
| `/알림추가` | 가격 알림 등록 | `/알림추가 KRW-BTC 이상 100000000` |
| `/알림목록` | 설정된 알림 목록 | `/알림목록` |
| `/알림삭제` | 알림 삭제 | `/알림삭제 1` |

## 자동 스케줄

- **매일 09:00 KST** → #뉴스리포트 + #시장지표 자동 전송
- **5분마다** → 가격 알림 조건 체크 → 충족 시 #가격알림에 전송
