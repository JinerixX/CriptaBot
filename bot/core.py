"""
core.py — инициализация бота и логирования
Совместимо с aiogram ≥ 3.7.0
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from logging.handlers import RotatingFileHandler   #  <<< NEW

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from dotenv import load_dotenv

# ─────────────────────────── env & dirs ────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")

BOT_TOKEN = os.getenv("TG_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TG_TOKEN is not set in the environment!")

LOG_DIR = BASE_DIR / "logs"                       #  <<< NEW
LOG_DIR.mkdir(exist_ok=True)                      #  <<< NEW
LOG_FILE = LOG_DIR / "criptabot.log"              #  <<< NEW

# ────────────────────────── logging setup ──────────────────────────
LOG_FMT = "[%(asctime)s] %(levelname)s:%(name)s — %(message)s"
DATE_FMT = "%Y-%m-%d %H:%M:%S"

# 1) console
console_handler = logging.StreamHandler()
console_handler.setFormatter(logging.Formatter(LOG_FMT, DATE_FMT))

# 2) rotating file 5 MB × 5 файлов                     #  <<< NEW
file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,   # 5 MB
    backupCount=5,              # scriptabot.log.1 … .5
    encoding="utf-8",
)
file_handler.setFormatter(logging.Formatter(LOG_FMT, DATE_FMT))

logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler],     #  <<< NEW
)

# ────────────────────────── aiogram objects ────────────────────────
bot = Bot(
    token=BOT_TOKEN,
    default=DefaultBotProperties(parse_mode="HTML"),
)
dp: Dispatcher = Dispatcher(bot=bot)
