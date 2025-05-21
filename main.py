from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

# ───────────────────────  make project importable  ──────────────────────
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ───────────────────────────  local imports  ────────────────────────────
from bot.db import already_seen, connect, db_is_empty, mark_seen
from bot.telegram import send
from bot.core import dp  # noqa: F401  (на будущее, если появятся хендлеры)

# CMS-анонсеры
from bot.ann_cms.binance import BinanceAnnouncer
from bot.ann_cms.bybit import BybitAnnouncer
from bot.ann_cms.okx import OKXAnnouncer
from bot.ann_cms.bitget import BitgetAnnouncer

# REST-fetchers
from bot.ann_api.binance import get_new_symbols as api_binance
from bot.ann_api.bybit import get_new_symbols as api_bybit
from bot.ann_api.okx import get_new_symbols as api_okx
from bot.ann_api.bitget import get_new_symbols as api_bitget
from bot.ann_api.symbol import Symbol  # dataclass

# ─────────────────────────────  settings  ───────────────────────────────
POLL_INTERVAL_API = int(os.getenv("POLL_INTERVAL_API", "60"))   # секунд
POLL_INTERVAL_CMS = int(os.getenv("POLL_INTERVAL_CMS", "90"))

CMS_ANNOUNCERS: Iterable[type] = (
    BinanceAnnouncer,
    BybitAnnouncer,
    OKXAnnouncer,
    BitgetAnnouncer,
)

API_FETCHERS: dict[str, callable[[], "asyncio.Future[List[Symbol]]"]] = {
    "Binance": api_binance,
    "Bybit": api_bybit,
    "OKX": api_okx,
    "Bitget": api_bitget,
}

# ──────────────────────────  bootstrap phase  ───────────────────────────
async def bootstrap(db) -> None:
    """Однократное наполнение пустой БД без уведомлений."""
    logging.info("Bootstrap: filling empty DB …")

    # 1. Записываем все текущие пары из REST-API
    for exchange, fetcher in API_FETCHERS.items():
        for sym in await fetcher():
            await mark_seen(db, exchange, sym.name, sym.market_type, "api")
    logging.info("Bootstrap: API pairs stored.")

    # 2. Записываем только будущие листинги из CMS
    now = datetime.now(timezone.utc)
    for cls in CMS_ANNOUNCERS:
        announcer = cls()
        async for ann in announcer.fetch():
            ts = getattr(ann, "listing_time", None) or getattr(
                ann, "starts_at", None
            )
            if ts is not None and ts <= now:
                continue  # событие уже прошло
            await mark_seen(db, ann.exchange, ann.symbol, "Unknown", "cms")
    logging.info("Bootstrap: CMS announcements stored.")
    logging.info("Bootstrap finished — monitoring starts.")

# ─────────────────────────────  runners  ────────────────────────────────
async def _runner_cms(cls, db):
    """Читает CMS-аннонсы, отправляет и логирует только будущие листинги."""
    announcer = cls()
    while True:
        async for ann in announcer.fetch():
            ts = getattr(ann, "listing_time", None) or getattr(
                ann, "starts_at", None
            )
            if ts is not None and ts <= datetime.now(timezone.utc):
                continue  # устарело
            market = "Unknown"
            if await already_seen(db, ann.exchange, ann.symbol, market):
                continue
            await mark_seen(db, ann.exchange, ann.symbol, market, "cms")
            logging.info("CMS new: %s — %s", ann.exchange, ann.symbol)
            await send(
                f"📰 <b>{ann.exchange}</b> планирует листинг "
                f"<code>{ann.symbol}</code>\n{ann.url}"
            )
        await asyncio.sleep(POLL_INTERVAL_CMS)


async def _runner_api(exchange: str, fetcher, db):
    """Опрашивает REST-API биржи, отправляет и логирует новые пары."""
    while True:
        for sym in await fetcher():
            if await already_seen(db, exchange, sym.name, sym.market_type):
                continue
            await mark_seen(db, exchange, sym.name, sym.market_type, "api")
            logging.info(
                "API new: %s — %s (%s)", exchange, sym.name, sym.market_type
            )
            await send(
                f"⚡️ <b>{exchange}</b> добавил пару "
                f"<code>{sym.name}</code> ({sym.market_type})"
            )
        await asyncio.sleep(POLL_INTERVAL_API)

# ───────────────────────────────  main  ────────────────────────────────
async def main() -> None:
    db = await connect()

    # Bootstrap, если база пуста
    if await db_is_empty(db):
        await bootstrap(db)

    tasks = [
        # CMS-анонсеры
        *(asyncio.create_task(_runner_cms(cls, db)) for cls in CMS_ANNOUNCERS),
        # REST-мониторинг
        *(
            asyncio.create_task(_runner_api(exch, fetcher, db))
            for exch, fetcher in API_FETCHERS.items()
        ),
        # Если появятся Telegram-хендлеры:
        # asyncio.create_task(dp.start_polling()),
    ]
    await asyncio.gather(*tasks)

# ──────────────────────────  entry-point  ───────────────────────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("CriptaBot stopped.")