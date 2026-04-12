"""금융 모듈 — 뉴스 리포트, 가격 알림, 시장 지표를 디스코드 채널로 전송"""

from __future__ import annotations

import logging
from datetime import datetime

import discord
from discord import app_commands
from discord.ext import commands
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
            value="\n".join(lines[:5]),
            inline=False,
        )

    return [main_embed]


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


class FinanceCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self):
        logger.info("Finance Cog ready")

    # ── News Report ──

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

    # ── Price Alerts ──

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
                    if alert.last_triggered_at:
                        elapsed = (datetime.utcnow() - alert.last_triggered_at).total_seconds()
                        if elapsed < 3600:
                            continue

                    embed = _build_alert_embed(alert.ticker, alert.condition, alert.threshold, current)
                    await channel.send(embed=embed)
                    alert.last_triggered_at = datetime.utcnow()
                    session.commit()
                    logger.info(f"Price alert triggered: {alert.ticker} {alert.condition} {alert.threshold}")

    @app_commands.command(name="알림추가", description="가격 알림 등록")
    @app_commands.describe(
        ticker="종목 티커 (예: KRW-BTC)",
        condition="조건",
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

        direction = "이상" if condition == "above" else "이하"
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

    # ── Market Indicators ──

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


async def setup(bot: commands.Bot):
    await bot.add_cog(FinanceCog(bot))
