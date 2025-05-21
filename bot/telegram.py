import logging
import os
from typing import Final

from aiogram.exceptions import TelegramAPIError

from bot.core import bot

CHAT_ID: Final[str | None] = os.getenv("CHAT_ID") or os.getenv("TG_CHAT_ID")

if CHAT_ID is None:
    raise RuntimeError("CHAT_ID (или TG_CHAT_ID) не задан в .env")

async def send(text: str) -> None:
    """
    Отправляет текстовое сообщение без превью ссылок.
    Используется всеми анонсерами.
    """
    try:
        await bot.send_message(
            chat_id=CHAT_ID,
            text=text.strip(),
            disable_web_page_preview=True,
        )
    except TelegramAPIError as exc:
        logging.exception("Failed to send message to Telegram: %s", exc)
