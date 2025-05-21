from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ─────────────────────── local imports ─────────────────────────────
from bot.db import (
    already_seen,
    connect,
    db_is_empty,
    mark_seen,
)
from bot.telegram import send
from bot.core import dp  # noqa: F401

# CMS-анонсеры
from bot.ann_cms.binance import BinanceAnnouncer
from bot.ann_cms.bybit import BybitAnnouncer
from bot.ann_cms.okx import OkxAnnouncer
from bot.ann_cms.bitget import BitgetAnnouncer

# API-фетчеры
from bot.ann_api.binance import get_new_symbols as api_binance
from bot.ann_api.bybit import get_new_symbols as api_bybit
from bot.ann_api.okx import get_new_symbols as api_okx
from bot.ann_api.bitget import get_new_symbols as api_bitget
from bot.ann_api.symbol import Symbol  # dataclass

# ───────────────────────── settings ───────────────────────────────
POLL_INTERVAL_API = int(os.getenv("POLL_INTERVAL_API", "60"))
POLL_INTERVAL_CMS = int(os.getenv("POLL_INTERVAL_CMS", "90"))

CMS_ANNOUNCERS: Iterable[type] = (
    BinanceAnnouncer,
    BybitAnnouncer,
    OkxAnnouncer,
    BitgetAnnouncer,
)

API_FETCHERS: dict[str, callable[[], "asyncio.Future[List[Symbol]]"]] = {
    "Binance": api_binance,
    "Bybit": api_bybit,
    "OKX": api_okx,
    "Bitget": api_bitget,
}

# ────────────────────────────────────────────────────────────────────────────
async def bootstrap(db) -> None:
    """Однократное наполнение базы без уведомлений."""
    logging.info("Bootstrap: filling empty DB…")

    # API — добавляем ВСЕ текущие пары
    for exchange, fetcher in API_FETCHERS.items():
        for sym in await fetcher():
            await mark_seen(db, exchange, sym.name, sym.market_type, "api")
    logging.info("Bootstrap: API pairs stored.")

    # CMS — добавляем ТОЛЬКО будущие листинги
    now = datetime.now(timezone.utc)
    for cls in CMS_ANNOUNCERS:
        ann = cls()
        async for item in ann.fetch():
            ts = getattr(item, "listing_time", None) or getattr(
                item, "starts_at", None
            )
            if ts is not None and ts <= now:
                continue  # событие уже прошло
            await mark_seen(db, item.exchange, item.symbol, "Unknown", "cms")
    logging.info("Bootstrap: CMS announcements stored.")
    logging.info("Bootstrap finished — monitoring starts.")

# ───────────────────────── runners ────────────────────────────────
async def _runner_cms(cls, db):
    announcer = cls()
    while True:
        async for ann in announcer.fetch():
            # игнорируем «прошедшие» листинги
            ts = getattr(ann, "listing_time", None) or getattr(ann, "starts_at", None)
            if ts is not None and ts <= datetime.now(timezone.utc):
                continue

            market = "Unknown"
            if await already_seen(db, ann.exchange, ann.symbol, market):
                continue
            await mark_seen(db, ann.exchange, ann.symbol, market, "cms")
            text = (
                f"📰 <b>{ann.exchange}</b> планирует листинг "
                f"<code>{ann.symbol}</code>\n{ann.url}"
            )
            await send(text)
        await asyncio.sleep(POLL_INTERVAL_CMS)


async def _runner_api(exchange: str, fetcher, db):
    while True:
        for sym in await fetcher():
            if await already_seen(db, exchange, sym.name, sym.market_type):
                continue
            await mark_seen(db, exchange, sym.name, sym.market_type, "api")
            text = (
                f"⚡️ <b>{exchange}</b> добавил пару "
                f"<code>{sym.name}</code> ({sym.market_type})"
            )
            await send(text)
        await asyncio.sleep(POLL_INTERVAL_API)

# ─────────────────────────── main ─────────────────────────────────
async def main() -> None:
    db = await connect()

    # Phase-0: bootstrap if DB is empty
    if await db_is_empty(db):
        await bootstrap(db)

    tasks = [
        *(asyncio.create_task(_runner_cms(cls, db)) for cls in CMS_ANNOUNCERS),
        *(
            asyncio.create_task(_runner_api(exch, fetcher, db))
            for exch, fetcher in API_FETCHERS.items()
        ),
        # asyncio.create_task(dp.start_polling()),  # future TG-handlers
    ]
    await asyncio.gather(*tasks)

# ───────────────────────── entrypoint ─────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] %(levelname)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("CriptaBot stopped.")
