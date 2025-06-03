from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from dateutil import parser as dtparse

# ───────────────────────── PYTHONPATH ─────────────────────────
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ───────────────────────── внутренние модули ───────────────────────
from bot.db import (
    already_seen,
    connect,
    db_is_empty,
    mark_seen,
    symbol_exists,
)
from bot.telegram import send
from bot.core import dp  # noqa: F401

# CMS- и API-анонcеры
from bot.ann_cms.binance import BinanceAnnouncer
from bot.ann_cms.bybit   import BybitAnnouncer
from bot.ann_cms.okx     import OkxAnnouncer
from bot.ann_cms.bitget  import BitgetAnnouncer

from bot.ann_api.wrappers import (
    BinanceApiAnnouncer,
    BybitApiAnnouncer,
    OkxApiAnnouncer,
    BitgetApiAnnouncer,
    API_ANNOUNCERS,
)

# ───────────────────────── интервалы ───────────────────────────
POLL_INTERVAL_API = int(os.getenv("POLL_INTERVAL_API", "60"))
POLL_INTERVAL_CMS = int(os.getenv("POLL_INTERVAL_CMS", "90"))

CMS_ANNOUNCERS: Iterable[type] = (
    BinanceAnnouncer,
    BybitAnnouncer,
    OkxAnnouncer,
    BitgetAnnouncer,
)

# ─────────────────────────── помощьники ────────────────────────────
DATE_RX1 = re.compile(r"\d{6}$")
DATE_RX2 = re.compile(r"-\d{2}[A-Z]{3}\d{2}$")

def is_dated_symbol(sym: str) -> bool:
    """
    True для символов типа "BTCUSD250613" или "BTCUSDT-13JUN25".
    Мы их игнорируем в REST (это futures).
    """
    return bool(DATE_RX1.search(sym) or DATE_RX2.search(sym))

def _get_url(ann) -> str:
    """
    Берёт ссылку из Announcement.details_url или .url.
    """
    return getattr(ann, "details_url", "")

def _fmt(ts) -> str:
    """
    Форматирует datetime в "03 Jun 2025 10:00 UTC".
    Если строка — возвращаем как есть.
    """
    if isinstance(ts, str):
        return ts
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.strftime("%d %b %Y %H:%M UTC")

def is_future(ts) -> bool:
    """
    True, если ts > текущий момент UTC.
    Принимает datetime или строку (пытаемся распарсить).
    """
    if ts is None:
        return False
    if isinstance(ts, str):
        try:
            ts = dtparse.parse(ts)
        except Exception:
            return False
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts > datetime.now(timezone.utc)


# ─────────────────────── bootstrap ────────────────────────────────
async def bootstrap(db):
    logging.info("Bootstrap: storing existing REST pairs …")
    # 1) Наполняем таблицу listings текущими парами из API (spot/perp)
    for cls in API_ANNOUNCERS:
        api = cls()
        async for sym in api.fetch():
            # игнорируем futures-символы
            if is_dated_symbol(sym.name):
                continue
            await mark_seen(db, api.exchange, sym.name, sym.market_type, "api")

    logging.info("Bootstrap: registering existing CMS announcements …")
    # 2) Пробегаем по всем существующим CMS-анонсерам и просто помечаем
    #    всё, что текущие fetch() возвращают (не отправляем в чат)
    for cls in CMS_ANNOUNCERS:
        cms = cls()
        async for ann in cms.fetch():
            # если пара уже в БД (любая market) — пропускаем
            if await symbol_exists(db, ann.exchange, ann.symbol):
                continue
            # иначе просто сохраняем без отправки
            await mark_seen(db, ann.exchange, ann.symbol, "Unknown", "cms")
            logging.debug("Bootstrap CMS registered: %s — %s", ann.exchange, ann.symbol)

    logging.info("Bootstrap finished.")


# ───────────────────── REST-runner ────────────────────────────────
async def _runner_api(cls, db):
    api = cls()
    while True:
        async for sym in api.fetch():
            if is_dated_symbol(sym.name):
                continue
            if await already_seen(db, api.exchange, sym.name, sym.market_type):
                continue
            await mark_seen(db, api.exchange, sym.name, sym.market_type, "api")

            # отправляем только новые API-пары
            await send(
                f"⚡️ <b>{api.exchange}</b> добавил пару "
                f"<code>{sym.name}</code> ({sym.market_type})"
            )
            logging.info("API new: %s — %s (%s)", api.exchange, sym.name, sym.market_type)
        await asyncio.sleep(POLL_INTERVAL_API)


# ───────────────────── CMS-runner ─────────────────────────────────
async def _runner_cms(cls, db):
    """
    Каждый CMS-анонсер, в бесконечном цикле, проверяет:
    • Если fetch() вернул ann, которого ещё нет в БД — отправляем и сохраняем.
    """
    cms = cls()
    while True:
        try:
            async for ann in cms.fetch():
                # Если уже есть в таблице — пропускаем
                if await already_seen(db, ann.exchange, ann.symbol, "Unknown"):
                    continue

                # Отправляем новый CMS-анонс в чат
                msg = f"📰 <b>{ann.exchange}</b> анонсировал листинг <code>{ann.symbol}</code>"
                url = _get_url(ann)
                if url:
                    msg += f"\n{url}"

                await send(msg)
                await mark_seen(db, ann.exchange, ann.symbol, "Unknown", "cms")
                logging.info("CMS sent: %s — %s", ann.exchange, ann.symbol)

        except Exception as exc:
            logging.error("CMS runner %s failed: %s", cls.__name__, exc)

        await asyncio.sleep(POLL_INTERVAL_CMS)


# ───────────────────────── main ────────────────────────────────────
async def main():
    db = await connect()
    if await db_is_empty(db):
        await bootstrap(db)

    tasks = [
        *(asyncio.create_task(_runner_api(c, db)) for c in API_ANNOUNCERS),
        *(asyncio.create_task(_runner_cms(c, db)) for c in CMS_ANNOUNCERS),
    ]
    await asyncio.gather(*tasks)


# ───────────────────────── entry-point ─────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s:%(name)s — %(message)s",
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("CryptoListingNotifyBot stopped.")