from __future__ import annotations

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
