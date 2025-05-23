from __future__ import annotations

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List

# ────────── путь корня ──────────
ROOT_DIR = Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# ────────── local imports ───────
from bot.db import already_seen, connect, db_is_empty, mark_seen
from bot.telegram import send
from bot.core import dp  # noqa: F401 (на будущее)

# CMS-анонсеры
from bot.ann_cms.binance import BinanceAnnouncer
from bot.ann_cms.bybit import BybitAnnouncer
from bot.ann_cms.okx import OkxAnnouncer
from bot.ann_cms.bitget import BitgetAnnouncer

# REST-fetchers
from bot.ann_api.binance import get_new_symbols as api_binance
from bot.ann_api.bybit   import get_new_symbols as api_bybit
from bot.ann_api.okx     import get_new_symbols as api_okx
from bot.ann_api.bitget  import get_new_symbols as api_bitget
from bot.ann_api.symbol  import Symbol

# ────────── настройки ───────────
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
    "Bybit":   api_bybit,
    "OKX":     api_okx,
    "Bitget":  api_bitget,
}

# ────────── helpers ─────────────
def _get_url(ann) -> str:
    """Возвращает первую найденную ссылку в объекте Announcement."""
    for field in ("url", "details_url", "announcement_url", "link"):
        val = getattr(ann, field, None)
        if val:
            return str(val)
    return ""

# ────────── bootstrap ───────────
async def bootstrap(db) -> None:
    logging.info("Bootstrap: filling empty DB …")

    # пары API
    for exch, fetcher in API_FETCHERS.items():
        for sym in await fetcher():
            await mark_seen(db, exch, sym.name, sym.market_type, "api")

    # будущие CMS-листинги
    now = datetime.now(timezone.utc)
    for cls in CMS_ANNOUNCERS:
        announcer = cls()
        async for ann in announcer.fetch():
            ts = getattr(ann, "listing_time", None) or getattr(ann, "starts_at", None)
            if ts and ts <= now:
                continue
            await mark_seen(db, ann.exchange, ann.symbol, "Unknown", "cms")

    logging.info("Bootstrap done — monitoring starts.")

# ────────── runners ─────────────
async def _runner_cms(cls, db):
    announcer = cls()
    while True:
        async for ann in announcer.fetch():
            ts = getattr(ann, "listing_time", None) or getattr(ann, "starts_at", None)
            if ts and ts <= datetime.now(timezone.utc):
                continue
            market = "Unknown"
            if await already_seen(db, ann.exchange, ann.symbol, market):
                continue
            await mark_seen(db, ann.exchange, ann.symbol, market, "cms")
            logging.info("CMS new: %s — %s", ann.exchange, ann.symbol)

            # собираем сообщение
            url = _get_url(ann)
            msg = (
                f"📰 <b>{ann.exchange}</b> планирует листинг "
                f"<code>{ann.symbol}</code>"
            )
            if url:
                msg += f"\n{url}"

            await send(msg)
        await asyncio.sleep(POLL_INTERVAL_CMS)


async def _runner_api(exchange: str, fetcher, db):
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

# ────────── main ────────────────
async def main() -> None:
    db = await connect()
    if await db_is_empty(db):
        await bootstrap(db)

    tasks = [
        *(asyncio.create_task(_runner_cms(cls, db)) for cls in CMS_ANNOUNCERS),
        *(
            asyncio.create_task(_runner_api(ex, fn, db))
            for ex, fn in API_FETCHERS.items()
        ),
        # asyncio.create_task(dp.start_polling()),  # future
    ]
    await asyncio.gather(*tasks)

# ────────── entry ───────────────
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("CriptaBot stopped.")