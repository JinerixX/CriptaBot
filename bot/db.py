from __future__ import annotations

import pathlib
import re
from typing import Final

import aiosqlite

# ────────────────────── path & schema ──────────────────────
DB_PATH: Final[pathlib.Path] = pathlib.Path("data") / "listings.db"

SCHEMA_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS listings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange  TEXT NOT NULL,
    symbol    TEXT NOT NULL,
    market    TEXT NOT NULL,            -- spot / perp / Unknown
    source    TEXT NOT NULL,            -- api | cms
    created   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, symbol, market)
);
"""

# ────────────────────── helpers ────────────────────────────
_RX_CLEAN = re.compile(r"[^A-Z0-9]")
def norm(sym: str) -> str:
    """
    BTC/USDT , btc_usdt , btcusdt  →  BTCUSDT
    Убираем слэши, дефисы, подчёркивания, переводим в верхний регистр.
    """
    return _RX_CLEAN.sub("", sym.upper())


async def connect() -> aiosqlite.Connection:
    DB_PATH.parent.mkdir(exist_ok=True)
    db = await aiosqlite.connect(DB_PATH)
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")
    await db.execute(SCHEMA_SQL)
    await db.commit()
    return db


async def db_is_empty(db) -> bool:
    async with db.execute("SELECT 1 FROM listings LIMIT 1;") as cur:
        return (await cur.fetchone()) is None


async def already_seen(db, exch: str, sym: str, mkt: str) -> bool:
    sym = norm(sym)
    q = "SELECT 1 FROM listings WHERE exchange=? AND symbol=? AND market=? LIMIT 1"
    async with db.execute(q, (exch, sym, mkt)) as cur:
        return (await cur.fetchone()) is not None


async def symbol_exists(db, exch: str, sym: str) -> bool:
    """
    Есть ли символ на бирже exch в ЛЮБОМ рынке?
    Используется CMS-раннером, чтобы понять, торгуется ли пара.
    """
    sym = norm(sym)
    async with db.execute(
        "SELECT 1 FROM listings WHERE exchange=? AND symbol=? LIMIT 1",
        (exch, sym),
    ) as cur:
        return (await cur.fetchone()) is not None


async def mark_seen(
    db,
    exch: str,
    sym: str,
    mkt: str,
    src: str,  # api | cms
) -> None:
    sym = norm(sym)
    await db.execute(
        "INSERT OR IGNORE INTO listings(exchange,symbol,market,source) VALUES(?,?,?,?)",
        (exch, sym, mkt, src),
    )
    await db.commit()
