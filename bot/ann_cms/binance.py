from __future__ import annotations

import os
import re
from typing import AsyncIterator

import httpx

from ann_cms.base import AbstractAnnouncer, Announcement

URL = (
    "https://www.binance.com/bapi/composite/v1/public/cms/article/"
    "catalog/list/query"
)
PARAMS = {
    "catalogId": 48,
    "pageNo": 1,
    "pageSize": 40,
}
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "clienttype": "web",
    "Accept-Language": "en-US,en;q=0.9",
}
if api_key := os.getenv("BINANCE_API_KEY"):
    HEADERS["X-MBX-APIKEY"] = api_key

# regex to capture ticker inside parentheses OR before USDT/USDC pair suffix
TICKER_RX = re.compile(
    r"\((?P<sym>[A-Z0-9_-]{2,15})\)"  # (ALT)
    r"|"
    r"(?P<pair>[A-Z0-9_-]{2,15})(?:USDT|USDC)",
    re.IGNORECASE,
)
SUFFIXES = ("USDT", "USDC")
# regex to filter only future listing announcements
UPCOMING_RX = re.compile(r"\bWill\s+(List|Add)\b", re.IGNORECASE)

class BinanceAnnouncer(AbstractAnnouncer):
    name = "Binance"

    async def fetch(self) -> AsyncIterator[Announcement]:
        async with httpx.AsyncClient(timeout=15, headers=HEADERS) as client:
            resp = await client.get(URL, params=PARAMS)
            resp.raise_for_status()
            data = resp.json().get("data", {})

        articles = data.get("articles", []) or data.get("articleList", [])
        for art in articles:
            title: str = art.get("title", "")
            # step 1 – keep only upcoming listings
            if not UPCOMING_RX.search(title):
                continue
            # step 2 – extract ticker
            m = TICKER_RX.search(title)
            if not m:
                continue
            raw = (m.group("sym") or m.group("pair") or "").upper()
            for suf in SUFFIXES:
                if raw.endswith(suf):
                    raw = raw[: -len(suf)]
                    break
            symbol = raw

            code = art.get("code") or art.get("id")
            url = (
                f"https://www.binance.com/en/support/announcement/detail/{code}"
                if code else art.get("url")
            )
            yield Announcement(self.name, symbol, url)