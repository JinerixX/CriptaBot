"""
core.py — единая точка инициализации бота и логирования
"""
import logging
import os
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# ────────────────────────  env & logging  ──────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")            # ищем .env в корне проекта

BOT_TOKEN = os.getenv("TG_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TG_TOKEN is not set in the environment!")

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s:%(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

# ───────────────────────  aiogram objects  ─────────────────────────
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),  # ← корректный способ
)
dp: Dispatcher = Dispatcher(bot=bot)