from __future__ import annotations

import re
from typing import AsyncIterator

import httpx

from ann_cms.base import AbstractAnnouncer, Announcement

API_URL = "https://api.bitget.com/api/v2/public/annoucements"
PARAMS = {
    "language": "en_US",
    "annType": "coin_listings",
    "limit": 10,
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    ),
    "Accept": "application/json",
}

TICKER_RX = re.compile(
    r"\((?P<sym>[A-Z0-9_-]{2,15})\)|(?P<pair>[A-Z0-9_-]{2,15})(?:USDT|USDC|PERP)",
    re.IGNORECASE,
)
SUFFIXES = ("USDT", "USDC", "PERP")
UPCOMING_RX = re.compile(r"Will\s+List|New Listing|Initial Listing|Launch", re.IGNORECASE)

class BitgetAnnouncer(AbstractAnnouncer):
    name = "Bitget"

    async def fetch(self) -> AsyncIterator[Announcement]:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            resp = await client.get(API_URL, params=PARAMS)
            resp.raise_for_status()
            data = resp.json()

        if str(data.get("code")) != "00000":
            return

        for art in data.get("data", []):
            title: str = art.get("annTitle", "")
            if not UPCOMING_RX.search(title):
                continue
            m = TICKER_RX.search(title)
            if not m:
                continue
            raw = (m.group("sym") or m.group("pair") or "").upper()
            for suf in SUFFIXES:
                if raw.endswith(suf):
                    raw = raw[: -len(suf)]
                    break
            symbol = raw
            url = art.get("annUrl")
            if url:
                yield Announcement(self.name, symbol, url)