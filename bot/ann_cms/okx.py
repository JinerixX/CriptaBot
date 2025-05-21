from __future__ import annotations

import re
from typing import AsyncIterator

import httpx
from bs4 import BeautifulSoup

from ann_cms.base import AbstractAnnouncer, Announcement

URL = "https://www.okx.com/help/section/announcements-new-listings"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TICKER_RX = re.compile(
    r"\((?P<sym>[A-Z0-9_-]{2,15})\)"          # (ALT)
    r"|"
    r"(?P<pair>[A-Z0-9_-]{2,15})(?:USDT|USDC)",  # ALTUSDT
    re.IGNORECASE,
)
UPCOMING_RX = re.compile(r"Will\s+List|Token Listing", re.IGNORECASE)
SUFFIXES = ("USDT", "USDC")


class OkxAnnouncer(AbstractAnnouncer):
    name = "OKX"

    async def fetch(self) -> AsyncIterator[Announcement]:
        async with httpx.AsyncClient(timeout=20, headers=HEADERS) as client:
            r = await client.get(URL, follow_redirects=True)
            r.raise_for_status()
            soup = BeautifulSoup(r.text, "html.parser")

        # карточки списка: <a class="article-item" href="/help/article/...">
        for a in soup.select("a.article-item"):
            title = a.get_text(" ", strip=True)
            if not UPCOMING_RX.search(title):
                continue  # не будущий листинг

            m = TICKER_RX.search(title)
            if not m:
                continue
            raw = (m.group("sym") or m.group("pair") or "").upper()
            for suf in SUFFIXES:
                if raw.endswith(suf):
                    raw = raw[: -len(suf)]
                    break
            symbol = raw

            href = a.get("href", "")
            url = href if href.startswith("http") else f"https://www.okx.com{href}"
            yield Announcement(self.name, symbol, url)