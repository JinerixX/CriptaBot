from __future__ import annotations

import re
from typing import AsyncIterator

import httpx

from ann_cms.base import AbstractAnnouncer, Announcement

API_URL = "https://api.bybit.com/v5/announcements/index"
PARAMS = {
    "locale": "en-US",
    "type": "new_crypto",  # listings only
    "page": 1,
    "limit": 50,
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    ),
    "Accept": "application/json",
}

# Extract ticker from (TICKER) or TICKERUSDT/USDC
TICKER_RX = re.compile(
    r"\((?P<sym>[A-Z0-9_-]{2,15})\)"  # (ARB)
    r"|"
    r"(?P<pair>[A-Z0-9_-]{2,15})(?:USDT|USDC)",
    re.IGNORECASE,
)
SUFFIXES = ("USDT", "USDC")
UPCOMING_RX = re.compile(r"New Listing", re.IGNORECASE)

class BybitAnnouncer(AbstractAnnouncer):
    name = "Bybit"

    async def fetch(self) -> AsyncIterator[Announcement]:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            resp = await client.get(API_URL, params=PARAMS)
            resp.raise_for_status()
            data = resp.json()

        if data.get("retCode") != 0:
            return  # maintenance or error

        articles = data.get("result", {}).get("list", [])
        for art in articles:
            title: str = art.get("title", "")
            if not UPCOMING_RX.search(title):
                continue  # skip non‑listing news

            m = TICKER_RX.search(title)
            if not m:
                continue
            raw = (m.group("sym") or m.group("pair") or "").upper()
            for suf in SUFFIXES:
                if raw.endswith(suf):
                    raw = raw[: -len(suf)]
                    break
            symbol = raw

            url = art.get("url")
            yield Announcement(self.name, symbol, url)