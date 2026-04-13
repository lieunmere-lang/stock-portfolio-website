# 보안 개선 TODO (사용자 액션 필요)

## 이미 적용된 것 (자동)

- [x] 보안 헤더 추가 (X-Frame-Options, X-Content-Type-Options, HSTS, XSS-Protection 등)
- [x] Swagger/ReDoc API 문서 비활성화 (외부 노출 방지)
- [x] 로그인 실패 시 남은 시도 횟수 비노출 (정보 유출 방지)
- [x] 로그인 성공/실패 로깅 추가 (보안 감사 추적)
- [x] JWT 토큰 만료 7일 → 1일로 단축
- [x] `.env`는 `.gitignore`에 포함되어 git에 추적되지 않음 (확인 완료)

---

## 사용자가 해야 할 일

### 1. JWT_SECRET_KEY 설정 (중요도: 높음)
현재 서버 재시작 시 JWT 키가 랜덤 생성되어 기존 토큰이 무효화됩니다.

**방법:** `backend/.env`에 아래 추가:
```
JWT_SECRET_KEY=여기에_랜덤_64자리_문자열_입력
```

생성 방법 (터미널에서):
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### 2. 비밀번호 변경 (중요도: 높음)
현재 비밀번호를 더 강력한 것으로 변경하세요.

**방법:** `backend/.env`에서:
```
APP_PASSWORD=최소12자_대소문자숫자특수문자_조합
```

### 3. API 키 점검 (중요도: 중간)
`.env` 파일의 API 키들이 외부에 노출된 적 없는지 확인하세요:
- UPBIT_ACCESS_KEY / UPBIT_SECRET_KEY
- KIWOOM_APP_KEY / KIWOOM_APP_SECRET  
- ANTHROPIC_API_KEY
- ALPHA_VANTAGE_API_KEY

만약 git 히스토리에 `.env`가 포함된 적 있다면:
1. 모든 API 키를 **즉시 재발급**
2. git 히스토리에서 제거: `git filter-branch` 또는 `BFG Repo-Cleaner` 사용

확인 방법:
```bash
git log --all --full-history -- backend/.env
```
결과가 나오면 히스토리에 포함된 것이므로 키 재발급 필요.

### 4. ngrok 인증 추가 (중요도: 중간)
ngrok URL은 누구나 접근 가능합니다. 추가 인증을 설정하세요.

**방법:** `manage_server.sh`에서 ngrok 실행 시:
```bash
ngrok http 8000 --basic-auth "사용자명:비밀번호"
```

### 5. 주기적으로 할 일
- [ ] 3개월마다 비밀번호 변경
- [ ] 6개월마다 API 키 재발급
- [ ] 서버 로그 주기적 확인: `./manage_server.sh logs`
