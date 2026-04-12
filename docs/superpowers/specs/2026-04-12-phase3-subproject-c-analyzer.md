# Phase 3 서브프로젝트 C: Claude API 뉴스 분석기 — 설계 문서

## 1. 개요

수집된 원시 뉴스(RawNewsItem)와 보유 종목 정보를 Claude API에 전달하여, 중요 뉴스 선별·한국어 요약·포트폴리오 영향 분석 리포트를 생성한다.

## 2. 흐름

```
collect_all() → RawNewsItem N건
    ↓
analyze_news(raw_items, holdings)
    ├─ 프롬프트 구성 (원시 뉴스 + 보유 종목)
    ├─ Claude API 호출 (Anthropic Python SDK)
    ├─ JSON 응답 파싱
    └─ 리포트 dict 반환
```

## 3. 함수 시그니처

```python
async def analyze_news(
    raw_items: List[RawNewsItem],
    holdings: List[Dict[str, Any]],
) -> Dict[str, Any]
```

### 입력

- `raw_items`: `collect_all()`이 반환한 원시 뉴스 리스트
- `holdings`: 보유 종목 리스트. 각 항목:
  ```json
  {"ticker": "TSLA", "name": "Tesla", "profit_loss_rate": 0.15}
  ```

### 출력

```json
{
    "summary": "전체 요약 텍스트 (한국어)",
    "model_used": "claude-haiku-4-5-20251001",
    "items": [
        {
            "category": "macro|stock|crypto|sentiment|hiring",
            "title": "한국어 제목",
            "summary": "한국어 요약 (2~3문장)",
            "impact_analysis": "포트폴리오 영향 분석 (해당 시)" or null,
            "related_ticker": "TSLA" or null,
            "source": "reuters",
            "source_url": "https://...",
            "importance": 5
        }
    ]
}
```

## 4. 프롬프트 설계

### System Prompt

```
너는 개인 투자자의 포트폴리오 뉴스 분석가다.

## 역할
- 제공된 원시 뉴스에서 투자에 중요한 뉴스 10~15건을 선별한다.
- 각 뉴스를 한국어로 요약하고 카테고리를 분류한다.
- 보유 종목과 관련된 뉴스에는 포트폴리오 영향 분석을 추가한다.
- 전체 시장 상황을 2~3문장으로 요약한다.

## 카테고리
- macro: 거시경제, 금리, 환율, 지정학
- stock: 주식 종목 관련
- crypto: 암호화폐 관련
- sentiment: 시장 심리, 소셜 트렌드
- hiring: 채용, 기업 트렌드

## 중요도 (1-5)
- 5: 포트폴리오에 직접 영향, 긴급
- 4: 시장 전반에 중요
- 3: 참고할 만함
- 2: 배경 정보
- 1: 부수적

## 응답 형식
반드시 JSON으로만 응답한다. 다른 텍스트를 포함하지 않는다.
```

### User Message

```
## 보유 종목
{holdings JSON}

## 수집된 뉴스 ({N}건)
{뉴스 목록: source, title, content, url}

위 뉴스에서 중요한 뉴스를 최대 {max_items}건 선별하여 분석하라.
```

### 응답 JSON 스키마

```json
{
    "summary": "string",
    "items": [
        {
            "category": "string",
            "title": "string",
            "summary": "string",
            "impact_analysis": "string|null",
            "related_ticker": "string|null",
            "source": "string",
            "source_url": "string",
            "importance": "integer"
        }
    ]
}
```

## 5. 환경 변수

```env
ANTHROPIC_API_KEY=sk-ant-...
NEWS_CLAUDE_MODEL=claude-haiku-4-5-20251001
NEWS_MAX_ITEMS=15
```

- `ANTHROPIC_API_KEY`: 필수. 미설정 시 로그 경고 후 빈 리포트 반환.
- `NEWS_CLAUDE_MODEL`: 기본값 `claude-haiku-4-5-20251001`. `.env`에서 변경 가능.
- `NEWS_MAX_ITEMS`: 선별 최대 건수. 기본값 15.

## 6. 에러 처리

| 상황 | 처리 |
|------|------|
| API 키 미설정 | 로그 경고 후 빈 리포트 dict 반환 (`summary: ""`, `items: []`) |
| API 호출 실패 | 예외 전파 (호출자가 처리) |
| JSON 파싱 실패 | 로그 경고 후 빈 리포트 dict 반환 |
| 원시 뉴스 0건 | 빈 리포트 dict 반환 |

## 7. 의존성

`requirements.txt`에 추가:
- `anthropic` — Anthropic Python SDK

## 8. 변경 파일

| 파일 | 변경 |
|------|------|
| `backend/requirements.txt` | `anthropic` 추가 |
| `backend/services/news_analyzer.py` | 기존 뼈대(NotImplementedError)를 실제 구현으로 교체 |
