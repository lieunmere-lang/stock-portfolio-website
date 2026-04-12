# Discord 금융 봇 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** discord.py 기반 금융 봇을 FastAPI 서버에 통합하여, 뉴스 리포트/가격 알림/시장 지표를 디스코드 서버 채널로 전송한다.

**Architecture:** FastAPI와 discord.py 봇이 같은 프로세스에서 비동기로 실행된다. 봇은 Cog(모듈) 기반 플러그인 구조로, `backend/bot/cogs/` 폴더에 모듈 파일을 추가하면 자동 로드된다. 금융 모듈(finance.py)이 뉴스/알림/지표 기능을 담당한다.

**Tech Stack:** discord.py>=2.3, APScheduler (기존), SQLAlchemy (기존), FastAPI (기존)

**Spec:** `docs/superpowers/specs/2026-04-12-discord-finance-bot-design.md`

---

## File Structure

```
backend/
├── main.py                    # 수정: Discord 봇 실행 추가
├── scheduler.py               # 수정: 디스코드 전송 훅 추가
├── database.py                # 수정: BotConfig 모델 추가, PriceAlert 필드 추가
├── requirements.txt           # 수정: discord.py 추가
├── bot/                       # 🆕 새 디렉토리
│   ├── __init__.py            # 🆕 봇 패키지
│   ├── client.py              # 🆕 봇 클라이언트, Cog 자동 로드
│   └── cogs/                  # 🆕 모듈 디렉토리
│       ├── __init__.py        # 🆕
│       └── finance.py         # 🆕 금융 모듈 (뉴스, 알림, 지표)
├── routers/
│   └── alerts.py              # 🆕 가격 알림 REST API (웹 UI용)
└── services/
    └── indicators.py          # 🆕 시장 지표 수집 서비스
```

---

### Task 1: 의존성 추가 및 DB 모델 확장

**Files:**
- Modify: `backend/requirements.txt`
- Modify: `backend/database.py:110-118` (PriceAlert 수정)
- Modify: `backend/database.py:184-200` (init_db 수정)

- [ ] **Step 1: requirements.txt에 discord.py 추가**

`backend/requirements.txt` 끝에 추가:
```
discord.py>=2.3
```

- [ ] **Step 2: pip install 실행**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && pip install discord.py>=2.3`
Expected: Successfully installed discord.py

- [ ] **Step 3: database.py에 BotConfig 모델 추가**

`backend/database.py`의 `TradeRecord` 클래스 뒤(line 181 이후)에 추가:

```python
class BotConfig(Base):
    __tablename__ = "bot_config"
    id = Column(Integer, primary_key=True)
    module_name = Column(String(50), nullable=False)      # "finance.news", "finance.alert" 등
    channel_id = Column(String(30), nullable=False)        # 디스코드 채널 ID
    config_json = Column(Text, default="{}")               # 모듈별 설정 (JSON)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
```

- [ ] **Step 4: PriceAlert 모델에 notification_sent 필드 추가**

`backend/database.py`의 `PriceAlert` 클래스에 중복 알림 방지 필드 추가:

```python
class PriceAlert(Base):
    __tablename__ = "price_alerts"
    id = Column(Integer, primary_key=True)
    ticker = Column(String(20), nullable=False)
    condition = Column(String(10), nullable=False)   # "above" | "below"
    threshold = Column(Float, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_triggered_at = Column(DateTime, nullable=True)  # 🆕 마지막 발동 시각
```

- [ ] **Step 5: init_db()에 마이그레이션 추가**

`backend/database.py`의 `init_db()` 함수 끝에 ALTER TABLE 추가:

```python
    migrations = [
        # 기존 마이그레이션들...
        "ALTER TABLE price_alerts ADD COLUMN last_triggered_at DATETIME",
    ]
    with engine.connect() as conn:
        for sql in migrations:
            try:
                conn.execute(text(sql))
                conn.commit()
            except Exception:
                conn.rollback()
```

- [ ] **Step 6: 서버 시작해서 테이블 생성 확인**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python -c "from database import init_db; init_db(); print('OK')"`
Expected: OK (에러 없이 테이블 생성)

- [ ] **Step 7: 커밋**

```bash
git add backend/requirements.txt backend/database.py
git commit -m "feat: add discord.py dependency and BotConfig model"
```

---

### Task 2: 봇 클라이언트 기본 구조

**Files:**
- Create: `backend/bot/__init__.py`
- Create: `backend/bot/client.py`
- Create: `backend/bot/cogs/__init__.py`

- [ ] **Step 1: bot 패키지 생성**

`backend/bot/__init__.py`:
```python
from bot.client import bot, start_bot, stop_bot

__all__ = ["bot", "start_bot", "stop_bot"]
```

- [ ] **Step 2: bot/cogs/__init__.py 생성**

`backend/bot/cogs/__init__.py`:
```python
# Cog modules are auto-loaded by client.py
```

- [ ] **Step 3: bot/client.py 작성**

`backend/bot/client.py`:
```python
import os
import asyncio
import logging
from pathlib import Path

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)


@bot.event
async def on_ready():
    logger.info(f"Discord bot logged in as {bot.user} (ID: {bot.user.id})")
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")


async def _load_cogs():
    """cogs/ 디렉토리의 모든 Cog을 자동 로드"""
    cogs_dir = Path(__file__).parent / "cogs"
    for file in cogs_dir.glob("*.py"):
        if file.name.startswith("_"):
            continue
        module = f"bot.cogs.{file.stem}"
        try:
            await bot.load_extension(module)
            logger.info(f"Loaded cog: {module}")
        except Exception as e:
            logger.error(f"Failed to load cog {module}: {e}")


_bot_task: asyncio.Task | None = None


async def start_bot():
    """FastAPI lifespan에서 호출. 봇을 백그라운드 태스크로 실행."""
    global _bot_task
    token = os.getenv("DISCORD_BOT_TOKEN")
    if not token:
        logger.warning("DISCORD_BOT_TOKEN not set — Discord bot disabled")
        return
    await _load_cogs()
    _bot_task = asyncio.create_task(bot.start(token))
    logger.info("Discord bot task started")


async def stop_bot():
    """FastAPI shutdown에서 호출."""
    global _bot_task
    if _bot_task and not _bot_task.done():
        await bot.close()
        _bot_task = None
        logger.info("Discord bot stopped")
```

- [ ] **Step 4: 봇 토큰 없이 import 테스트**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python -c "from bot.client import bot, start_bot, stop_bot; print('import OK')"`
Expected: import OK

- [ ] **Step 5: 커밋**

```bash
git add backend/bot/
git commit -m "feat: add Discord bot client with auto cog loading"
```

---

### Task 3: FastAPI에 봇 통합

**Files:**
- Modify: `backend/main.py:61-69` (lifespan 수정)

- [ ] **Step 1: main.py에 봇 import 추가**

`backend/main.py` 상단 import에 추가:
```python
from bot import start_bot, stop_bot
```

- [ ] **Step 2: lifespan에 봇 시작/종료 추가**

기존 lifespan 이벤트를 수정. `main.py`의 lifespan 컨텍스트 매니저에서:

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    start_scheduler()
    await start_bot()
    yield
    stop_scheduler()
    await stop_bot()
```

참고: 기존 lifespan이 `@app.on_event("startup")`/`@app.on_event("shutdown")` 패턴이면 asynccontextmanager 패턴으로 교체해야 함. 현재 main.py 구조를 확인하고 적절히 수정.

- [ ] **Step 3: 서버 시작 테스트 (토큰 없이)**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && timeout 5 python -c "import asyncio; from bot.client import start_bot; asyncio.run(start_bot()); print('OK')" 2>&1 || true`
Expected: WARNING — DISCORD_BOT_TOKEN not set (봇은 비활성화되지만 서버는 정상 실행)

- [ ] **Step 4: ��밋**

```bash
git add backend/main.py
git commit -m "feat: integrate Discord bot into FastAPI lifespan"
```

---

### Task 4: 시장 지표 수집 서비스

**Files:**
- Create: `backend/services/indicators.py`

- [ ] **Step 1: indicators.py 작성**

`backend/services/indicators.py`:
```python
"""시장 지표 수집 서비스 — 공포탐욕지수, VIX, BTC 도미넌스, 원/달러 환율"""

import logging
from dataclasses import dataclass
from typing import Optional

import httpx

logger = logging.getLogger(__name__)


@dataclass
class MarketIndicators:
    fear_greed_index: Optional[int] = None       # 0-100
    fear_greed_label: Optional[str] = None       # "Extreme Fear", "Fear", "Neutral", "Greed", "Extreme Greed"
    vix: Optional[float] = None
    btc_dominance: Optional[float] = None        # percentage
    usd_krw: Optional[float] = None


async def fetch_indicators() -> MarketIndicators:
    """모든 시장 지표를 한 번에 수집"""
    indicators = MarketIndicators()

    async with httpx.AsyncClient(timeout=10) as client:
        # 공포탐욕지수
        try:
            resp = await client.get("https://api.alternative.me/fng/?limit=1")
            data = resp.json()["data"][0]
            indicators.fear_greed_index = int(data["value"])
            indicators.fear_greed_label = data["value_classification"]
        except Exception as e:
            logger.warning(f"Fear & Greed fetch failed: {e}")

        # BTC 도미넌스 (CoinGecko)
        try:
            resp = await client.get("https://api.coingecko.com/api/v3/global")
            data = resp.json()["data"]
            indicators.btc_dominance = round(data["market_cap_percentage"]["btc"], 1)
        except Exception as e:
            logger.warning(f"BTC dominance fetch failed: {e}")

        # VIX (Yahoo Finance)
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")
            if not hist.empty:
                indicators.vix = round(hist["Close"].iloc[-1], 2)
        except Exception as e:
            logger.warning(f"VIX fetch failed: {e}")

        # 원/달러 환율
        try:
            from services.stock import get_usd_krw
            indicators.usd_krw = get_usd_krw()
        except Exception as e:
            logger.warning(f"USD/KRW fetch failed: {e}")

    return indicators
```

- [ ] **Step 2: import 테스트**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python -c "from services.indicators import fetch_indicators, MarketIndicators; print('OK')"`
Expected: OK

- [ ] **Step 3: 커밋**

```bash
git add backend/services/indicators.py
git commit -m "feat: add market indicators service (fear&greed, VIX, BTC dominance, USD/KRW)"
```

---

### Task 5: 금융 Cog 모듈 — 뉴스 리포트 전송

**Files:**
- Create: `backend/bot/cogs/finance.py`

- [ ] **Step 1: finance.py Cog 기본 구조 + 뉴스 리포트 기능 작성**

`backend/bot/cogs/finance.py`:
```python
"""금융 모듈 — 뉴스 리포트, 가격 알림, 시장 지표를 디스코드 채널로 전송"""

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands, tasks
from sqlalchemy import desc
from sqlalchemy.orm import Session as SASession

from database import BotConfig, NewsReport, NewsReportItem, PriceAlert, engine

logger = logging.getLogger(__name__)


def _get_channel_id(module_name: str) -> int | None:
    """BotConfig에서 모듈의 채널 ID 조회"""
    with SASession(engine) as session:
        config = session.query(BotConfig).filter_by(
            module_name=module_name, is_active=True
        ).first()
        if config:
            return int(config.channel_id)
    return None


def _build_news_embed(report, items: list) -> list[discord.Embed]:
    """뉴스 리포트를 Discord Embed 리스트로 변환"""
    main_embed = discord.Embed(
        title=f"📊 모닝 리포트 — {report.report_date}",
        description=report.summary or "",
        color=discord.Color.blue(),
        timestamp=datetime.utcnow(),
    )
    main_embed.set_footer(text=f"수집 {report.total_collected}건 → 선별 {report.total_selected}건")

    categories = {
        "macro": ("🌍 매크로", []),
        "stock": ("📈 주식", []),
        "crypto": ("🪙 크립토", []),
        "sentiment": ("💭 센티먼트", []),
        "hiring": ("💼 채용/트렌드", []),
    }

    for item in items:
        cat = item.category.lower()
        if cat in categories:
            categories[cat][1].append(item)

    for cat_key, (label, cat_items) in categories.items():
        if not cat_items:
            continue
        lines = []
        for item in cat_items:
            stars = "⭐" * min(item.importance, 5)
            line = f"• **{item.title}** {stars}"
            if item.related_ticker:
                line += f" `{item.related_ticker}`"
            lines.append(line)
        main_embed.add_field(
            name=f"{label} ({len(cat_items)}건)",
            value="\n".join(lines[:5]),  # 최대 5건
            inline=False,
        )

    return [main_embed]


class FinanceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Finance Cog ready")

    async def send_news_report(self):
        """최신 뉴스 리포트를 디스코드 채널에 전송"""
        channel_id = _get_channel_id("finance.news")
        if not channel_id:
            logger.warning("finance.news channel not configured")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            logger.error(f"Channel {channel_id} not found")
            return

        with SASession(engine) as session:
            report = session.query(NewsReport).order_by(desc(NewsReport.id)).first()
            if not report:
                logger.info("No news report to send")
                return

            items = session.query(NewsReportItem).filter_by(report_id=report.id).all()
            embeds = _build_news_embed(report, items)

        await channel.send(embeds=embeds)
        logger.info(f"News report sent to channel {channel_id}")

    @app_commands.command(name="리포트", description="최신 뉴스 리포트 조회")
    async def report_command(self, interaction: discord.Interaction):
        await interaction.response.defer()

        with SASession(engine) as session:
            report = session.query(NewsReport).order_by(desc(NewsReport.id)).first()
            if not report:
                await interaction.followup.send("아직 생성된 리포트가 없어요.")
                return
            items = session.query(NewsReportItem).filter_by(report_id=report.id).all()
            embeds = _build_news_embed(report, items)

        await interaction.followup.send(embeds=embeds)


async def setup(bot: commands.Bot):
    await bot.add_cog(FinanceCog(bot))
```

- [ ] **Step 2: import 테스트**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python -c "from bot.cogs.finance import FinanceCog; print('OK')"`
Expected: OK

- [ ] **Step 3: 커밋**

```bash
git add backend/bot/cogs/finance.py
git commit -m "feat: add finance cog with news report embed and /리포��� command"
```

---

### Task 6: 금융 Cog — 가격 알림 기���

**Files:**
- Modify: `backend/bot/cogs/finance.py`

- [ ] **Step 1: finance.py에 가격 알림 헬퍼 함수 추가**

`_build_news_embed` 함수 뒤에 추가:

```python
def _build_alert_embed(ticker: str, condition: str, threshold: float, current_price: float) -> discord.Embed:
    """가격 알림 Embed 생성"""
    is_above = condition == "above"
    color = discord.Color.red() if is_above else discord.Color.green()
    direction = "돌파 ⬆️" if is_above else "하회 ⬇️"

    embed = discord.Embed(
        title=f"💰 가격 알림 — {ticker} {direction}",
        color=color,
        timestamp=datetime.utcnow(),
    )
    embed.add_field(name="현재가", value=f"₩{current_price:,.0f}", inline=True)
    embed.add_field(name="설정 조건", value=f"{condition} ₩{threshold:,.0f}", inline=True)
    return embed
```

- [ ] **Step 2: FinanceCog에 가격 알림 체크 메서드 추가**

`FinanceCog` 클래스에 추가:

```python
    async def check_price_alerts(self):
        """활성 가격 알림을 체크하고 조건 충족 시 전송"""
        channel_id = _get_channel_id("finance.alert")
        if not channel_id:
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        from services.upbit import fetch_upbit_assets

        try:
            assets = fetch_upbit_assets()
        except Exception as e:
            logger.error(f"Failed to fetch prices for alerts: {e}")
            return

        price_map = {a["ticker"]: a["current_price"] for a in assets}

        with SASession(engine) as session:
            alerts = session.query(PriceAlert).filter_by(is_active=True).all()
            for alert in alerts:
                current = price_map.get(alert.ticker)
                if current is None:
                    continue

                triggered = False
                if alert.condition == "above" and current >= alert.threshold:
                    triggered = True
                elif alert.condition == "below" and current <= alert.threshold:
                    triggered = True

                if triggered:
                    # 같은 알림이 1시간 내에 다시 발동되지 않도록
                    if alert.last_triggered_at:
                        elapsed = (datetime.utcnow() - alert.last_triggered_at).total_seconds()
                        if elapsed < 3600:
                            continue

                    embed = _build_alert_embed(alert.ticker, alert.condition, alert.threshold, current)
                    await channel.send(embed=embed)
                    alert.last_triggered_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Price alert triggered: {alert.ticker} {alert.condition} {alert.threshold}")
```

- [ ] **Step 3: 슬래시 명령어 추가 — /알림추가, /알림목록, /알림삭제**

`FinanceCog` 클래스에 추가:

```python
    @app_commands.command(name="알림추가", description="가격 알림 등록")
    @app_commands.describe(
        ticker="종목 티커 (예: KRW-BTC)",
        condition="조건 (above=이상, below=이하)",
        threshold="가격 (원)",
    )
    @app_commands.choices(condition=[
        app_commands.Choice(name="이상", value="above"),
        app_commands.Choice(name="이하", value="below"),
    ])
    async def add_alert(self, interaction: discord.Interaction, ticker: str, condition: str, threshold: float):
        ticker = ticker.upper()
        with SASession(engine) as session:
            alert = PriceAlert(ticker=ticker, condition=condition, threshold=threshold, is_active=True)
            session.add(alert)
            session.commit()
            alert_id = alert.id

        direction = "이상" if condition == "above" else "��하"
        await interaction.response.send_message(
            f"✅ 알림 등록 완료! (#{alert_id})\n`{ticker}` ₩{threshold:,.0f} {direction}"
        )

    @app_commands.command(name="알림목록", description="설정된 가격 알림 목록")
    async def list_alerts(self, interaction: discord.Interaction):
        with SASession(engine) as session:
            alerts = session.query(PriceAlert).filter_by(is_active=True).all()
            if not alerts:
                await interaction.response.send_message("설정된 알림이 없어요.")
                return

            lines = []
            for a in alerts:
                direction = "이상" if a.condition == "above" else "이하"
                lines.append(f"**#{a.id}** `{a.ticker}` ₩{a.threshold:,.0f} {direction}")

            embed = discord.Embed(
                title="💰 가격 알림 목록",
                description="\n".join(lines),
                color=discord.Color.gold(),
            )
            await interaction.response.send_message(embed=embed)

    @app_commands.command(name="알림삭제", description="가격 알림 삭제")
    @app_commands.describe(alert_id="삭제할 알림 번호")
    async def delete_alert(self, interaction: discord.Interaction, alert_id: int):
        with SASession(engine) as session:
            alert = session.query(PriceAlert).filter_by(id=alert_id, is_active=True).first()
            if not alert:
                await interaction.response.send_message(f"❌ 알림 #{alert_id}을(를) 찾을 수 없어요.")
                return
            alert.is_active = False
            session.commit()

        await interaction.response.send_message(f"🗑️ 알림 #{alert_id} 삭제 완료!")
```

- [ ] **Step 4: ���밋**

```bash
git add backend/bot/cogs/finance.py
git commit -m "feat: add price alert check and slash commands to finance cog"
```

---

### Task 7: 금융 Cog — 시장 지표 전송

**Files:**
- Modify: `backend/bot/cogs/finance.py`

- [ ] **Step 1: 시장 지표 Embed 빌더 추가**

`_build_alert_embed` 함수 뒤에 추가:

```python
def _build_indicators_embed(indicators) -> discord.Embed:
    """시장 지표를 Discord Embed로 변환"""
    embed = discord.Embed(
        title="📈 시장 지표",
        color=discord.Color.teal(),
        timestamp=datetime.utcnow(),
    )

    if indicators.fear_greed_index is not None:
        fg = indicators.fear_greed_index
        bar = "🟢" if fg >= 60 else "🟡" if fg >= 40 else "🔴"
        embed.add_field(
            name="공포탐욕지수",
            value=f"{bar} **{fg}** ({indicators.fear_greed_label})",
            inline=True,
        )

    if indicators.vix is not None:
        embed.add_field(name="VIX", value=f"**{indicators.vix}**", inline=True)

    if indicators.btc_dominance is not None:
        embed.add_field(name="BTC 도미넌스", value=f"**{indicators.btc_dominance}%**", inline=True)

    if indicators.usd_krw is not None:
        embed.add_field(name="원/달러", value=f"**₩{indicators.usd_krw:,.0f}**", inline=True)

    return embed
```

- [ ] **Step 2: FinanceCog에 시장 지표 전송 메서드 + 슬래시 명령어 추가**

`FinanceCog` 클래스에 추가:

```python
    async def send_indicators(self):
        """시장 지표를 디스코드 채널에 전송"""
        channel_id = _get_channel_id("finance.indicator")
        if not channel_id:
            logger.warning("finance.indicator channel not configured")
            return

        channel = self.bot.get_channel(channel_id)
        if not channel:
            return

        from services.indicators import fetch_indicators

        indicators = await fetch_indicators()
        embed = _build_indicators_embed(indicators)
        await channel.send(embed=embed)
        logger.info(f"Market indicators sent to channel {channel_id}")

    @app_commands.command(name="지표", description="현재 시장 지표 조회")
    async def indicators_command(self, interaction: discord.Interaction):
        await interaction.response.defer()

        from services.indicators import fetch_indicators

        indicators = await fetch_indicators()
        embed = _build_indicators_embed(indicators)
        await interaction.followup.send(embed=embed)
```

- [ ] **Step 3: ���밋**

```bash
git add backend/bot/cogs/finance.py backend/services/indicators.py
git commit -m "feat: add market indicators embed and /지표 command"
```

---

### Task 8: 스케줄러에 디스코드 전송 연동

**Files:**
- Modify: `backend/scheduler.py:363-461` (generate_news_report 수정)
- Modify: `backend/scheduler.py:476-500` (start_scheduler 수정)

- [ ] **Step 1: scheduler.py에 디스코드 전송 함수 추가**

`backend/scheduler.py`의 `generate_news_report()` 함수 뒤에 추가:

```python
def _send_discord_notifications():
    """뉴스 리포트 생성 후 디스코드로 전송 (09:00 KST 실행)"""
    import asyncio
    try:
        from bot.client import bot
        if bot.is_ready():
            cog = bot.get_cog("FinanceCog")
            if cog:
                loop = bot.loop
                asyncio.run_coroutine_threadsafe(cog.send_news_report(), loop)
                asyncio.run_coroutine_threadsafe(cog.send_indicators(), loop)
                logger.info("Discord notifications scheduled")
            else:
                logger.warning("FinanceCog not loaded")
        else:
            logger.warning("Discord bot not ready — skipping notifications")
    except Exception as e:
        logger.error(f"Discord notification error: {e}")


def _check_price_alerts():
    """5분마다 가격 알림 체크"""
    import asyncio
    try:
        from bot.client import bot
        if bot.is_ready():
            cog = bot.get_cog("FinanceCog")
            if cog:
                loop = bot.loop
                asyncio.run_coroutine_threadsafe(cog.check_price_alerts(), loop)
    except Exception as e:
        logger.error(f"Price alert check error: {e}")
```

- [ ] **Step 2: start_scheduler()에 새 job 등록**

`backend/scheduler.py`의 `start_scheduler()` 함수에 추가:

```python
    # 디스코드 뉴스 + 지표 전송 (09:00 KST)
    scheduler.add_job(
        _send_discord_notifications,
        "cron",
        hour=9,
        minute=0,
        timezone="Asia/Seoul",
        id="discord_notifications",
        replace_existing=True,
    )

    # 가격 알림 체크 (5분마다)
    scheduler.add_job(
        _check_price_alerts,
        "interval",
        minutes=5,
        id="check_price_alerts",
        replace_existing=True,
    )
```

- [ ] **Step 3: 커밋**

```bash
git add backend/scheduler.py
git commit -m "feat: integrate Discord notifications into scheduler (news 09:00, alerts every 5min)"
```

---

### Task 9: 가격 알림 REST API (웹 UI용)

**Files:**
- Create: `backend/routers/alerts.py`
- Modify: `backend/main.py` (라우터 등록)

- [ ] **Step 1: alerts.py 라우터 작성**

`backend/routers/alerts.py`:
```python
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session as SASession

from database import PriceAlert, engine

router = APIRouter(prefix="/api/alerts")


class AlertCreate(BaseModel):
    ticker: str
    condition: str   # "above" | "below"
    threshold: float


class AlertOut(BaseModel):
    id: int
    ticker: str
    condition: str
    threshold: float
    is_active: bool
    created_at: datetime
    last_triggered_at: Optional[datetime] = None


@router.get("/", response_model=list[AlertOut])
def list_alerts():
    with SASession(engine) as session:
        alerts = session.query(PriceAlert).filter_by(is_active=True).all()
        return [AlertOut(
            id=a.id, ticker=a.ticker, condition=a.condition,
            threshold=a.threshold, is_active=a.is_active,
            created_at=a.created_at, last_triggered_at=a.last_triggered_at,
        ) for a in alerts]


@router.post("/", response_model=AlertOut)
def create_alert(body: AlertCreate):
    with SASession(engine) as session:
        alert = PriceAlert(
            ticker=body.ticker.upper(),
            condition=body.condition,
            threshold=body.threshold,
            is_active=True,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)
        return AlertOut(
            id=alert.id, ticker=alert.ticker, condition=alert.condition,
            threshold=alert.threshold, is_active=alert.is_active,
            created_at=alert.created_at, last_triggered_at=alert.last_triggered_at,
        )


@router.delete("/{alert_id}")
def delete_alert(alert_id: int):
    with SASession(engine) as session:
        alert = session.query(PriceAlert).filter_by(id=alert_id, is_active=True).first()
        if not alert:
            return {"status": "not_found"}
        alert.is_active = False
        session.commit()
        return {"status": "deleted", "id": alert_id}
```

- [ ] **Step 2: main.py에 alerts 라우터 등록**

`backend/main.py`의 라우터 등록 부분에 추가:
```python
from routers.alerts import router as alerts_router

app.include_router(alerts_router, dependencies=[Depends(require_auth)])
```

- [ ] **Step 3: 커밋**

```bash
git add backend/routers/alerts.py backend/main.py
git commit -m "feat: add price alerts REST API for web UI"
```

---

### Task 10: .env 설정 및 최종 통합 테스트

**Files:**
- Modify: `backend/.env` (환경변수 추가)

- [ ] **Step 1: .env에 디스코드 환경변수 추가**

`backend/.env`에 추가:
```
DISCORD_BOT_TOKEN=    # Discord Developer Portal에서 발급
DISCORD_GUILD_ID=     # 디스코드 서버 ID
```

사용자가 직접 토큰과 서버 ID를 채워야 함.

- [ ] **Step 2: BotConfig 초기 데이터 삽입 스크립트 작성**

사용자가 채널 생성 후 실행할 설정 스크립트. `backend/setup_bot.py`:

```python
"""Discord 봇 채널 설정 스크립트. 채널 ID를 입력하면 BotConfig에 저장."""

from database import BotConfig, engine, init_db
from sqlalchemy.orm import Session

init_db()

print("=== Discord 금융봇 채널 설정 ===")
print("디스코드 서버에서 채널 ID를 복사해주세요.")
print("(채널 우클릭 → ID 복사, 개발자 모드 필요)\n")

modules = [
    ("finance.news", "#뉴스리포트 채널 ID"),
    ("finance.alert", "#가격알림 채널 ID"),
    ("finance.indicator", "#시장지표 채널 ID"),
]

with Session(engine) as session:
    for module_name, prompt in modules:
        channel_id = input(f"{prompt}: ").strip()
        if not channel_id:
            print(f"  → 건너뜀")
            continue

        existing = session.query(BotConfig).filter_by(module_name=module_name).first()
        if existing:
            existing.channel_id = channel_id
            existing.is_active = True
        else:
            session.add(BotConfig(module_name=module_name, channel_id=channel_id))

    session.commit()
    print("\n✅ 설정 완료!")
```

- [ ] **Step 3: 전체 import 체인 확인**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python -c "
from database import BotConfig, PriceAlert, init_db
from bot.client import bot, start_bot, stop_bot
from bot.cogs.finance import FinanceCog
from services.indicators import fetch_indicators
from routers.alerts import router
print('All imports OK')
"`
Expected: All imports OK

- [ ] **Step 4: 커���**

```bash
git add backend/.env backend/setup_bot.py
git commit -m "feat: add Discord bot setup script and env config"
```

---

### Task 11: 디스코드 봇 생성 가이드 (사용자 액션)

이 태스크는 코드가 아니라 사용자가 수행해야 하는 설정 단계입니다.

- [ ] **Step 1: Discord Developer Portal에서 봇 생성**

1. https://discord.com/developers/applications 접속
2. "New Application" → 이름: "금융봇" (또는 원하는 이름)
3. Bot 탭 → "Add Bot"
4. TOKEN → "Copy" → `.env`의 `DISCORD_BOT_TOKEN`에 붙여넣기
5. Privileged Gateway Intents → "Message Content Intent" 활성화

- [ ] **Step 2: 봇을 서버에 초대**

1. OAuth2 → URL Generator
2. Scopes: `bot`, `applications.commands`
3. Bot Permissions: `Send Messages`, `Embed Links`, `Read Message History`
4. 생성된 URL로 접속하여 서버에 봇 초대

- [ ] **Step 3: 디스코드 서버에 채널 생성**

1. 서버에서 "📈 금융" 카테고리 생성
2. 카테고리 안에 채널 생성: #뉴스리포트, #가격알림, #시장지표
3. 서버 ID와 각 채널 ID를 복사

- [ ] **Step 4: 설정 스크립트 실행**

Run: `cd /Users/bagdaehyeon/development_Workspace/stock_workspace/stock-portfolio-website/backend && python setup_bot.py`
채널 ID를 입력하여 BotConfig 설정

- [ ] **Step 5: 서버 시작 및 봇 동작 확인**

Run: `./manage_server.sh start`
디스코드 서버에서 봇이 온라인인지 확인하고, `/리포트`와 `/지표` 명령어 테스트
