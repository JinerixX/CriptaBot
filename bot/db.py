"""
bot/db.py
~~~~~~~~~
Единая обёртка над SQLite для CriptaBot.

• Файл БД: data/listings.db
• Таблица listings:
      id        – авто-PK
      exchange  – биржа (Binance | Bybit | …)
      symbol    – тикер (BTCUSDT …)
      market    – тип рынка (spot | futures | perp | Unknown)
      source    – cms | api
      created   – UTC-timestamp
   UNIQUE(exchange, symbol, market)  – исключает дубли.

Функции:
    connect()        → Connection         — открыть/создать БД, применить схему
    db_is_empty(db)  → bool               — есть ли хоть одна запись
    already_seen(db, exch, sym, mkt)      — True, если запись уже есть
    mark_seen(db, exch, sym, mkt, src)    — вставить, если ещё не было
"""

from __future__ import annotations

import pathlib
from typing import Final

import aiosqlite


# ────────────────────────────  Path & schema  ───────────────────────────
DB_PATH: Final[pathlib.Path] = pathlib.Path("data") / "listings.db"

SCHEMA_SQL: Final[str] = """
CREATE TABLE IF NOT EXISTS listings (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    exchange  TEXT NOT NULL,
    symbol    TEXT NOT NULL,
    market    TEXT NOT NULL,
    source    TEXT NOT NULL,            -- cms | api
    created   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(exchange, symbol, market)
);
"""


# ────────────────────────────  Helpers  ────────────────────────────────
async def connect() -> aiosqlite.Connection:
    """
    • Создаёт data/ при необходимости.
    • Открывает соединение в WAL-режиме (лучше параллелизм).
    • Применяет схему и отдаёт Connection.
    """
    DB_PATH.parent.mkdir(exist_ok=True)

    db = await aiosqlite.connect(DB_PATH)
    await db.execute("PRAGMA journal_mode=WAL;")
    await db.execute("PRAGMA foreign_keys=ON;")
    await db.execute(SCHEMA_SQL)
    await db.commit()
    return db


async def db_is_empty(db: aiosqlite.Connection) -> bool:
    """True, если таблица listings пуста."""
    async with db.execute("SELECT 1 FROM listings LIMIT 1;") as cur:
        return (await cur.fetchone()) is None


async def already_seen(
    db: aiosqlite.Connection,
    exchange: str,
    symbol: str,
    market: str,
) -> bool:
    """
    Проверяет, есть ли уже такая пара/листинг.
    """
    query = """
    SELECT 1
      FROM listings
     WHERE exchange = ?
       AND symbol   = ?
       AND market   = ?
     LIMIT 1;
    """
    async with db.execute(query, (exchange, symbol, market)) as cur:
        return (await cur.fetchone()) is not None


async def mark_seen(
    db: aiosqlite.Connection,
    exchange: str,
    symbol: str,
    market: str,
    source: str,  # "cms" | "api"
) -> None:
    """
    Пишет запись, если её ещё нет (INSERT OR IGNORE).
    """
    query = """
    INSERT OR IGNORE INTO listings (exchange, symbol, market, source)
    VALUES (?, ?, ?, ?);
    """
    await db.execute(query, (exchange, symbol, market, source))
    await db.commit()
