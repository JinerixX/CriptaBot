from typing import AsyncIterator, List

from bot.ann_api.binance import get_new_symbols as _binance
from bot.ann_api.bybit import get_new_symbols as _bybit
from bot.ann_api.okx import get_new_symbols as _okx
from bot.ann_api.bitget import get_new_symbols as _bitget
from bot.ann_api.symbol import Symbol


class _BaseApiAnnouncer:
    exchange: str

    async def _fetch_raw(self) -> List[Symbol]: ...

    async def fetch(self) -> AsyncIterator[Symbol]:
        """
        yield Symbol(...) один за другим
        """
        for sym in await self._fetch_raw():
            yield sym


class BinanceApiAnnouncer(_BaseApiAnnouncer):
    exchange = "Binance"
    _fetch_raw = staticmethod(_binance)


class BybitApiAnnouncer(_BaseApiAnnouncer):
    exchange = "Bybit"
    _fetch_raw = staticmethod(_bybit)


class OkxApiAnnouncer(_BaseApiAnnouncer):
    exchange = "OKX"
    _fetch_raw = staticmethod(_okx)


class BitgetApiAnnouncer(_BaseApiAnnouncer):
    exchange = "Bitget"
    _fetch_raw = staticmethod(_bitget)


API_ANNOUNCERS = (
    BinanceApiAnnouncer,
    BybitApiAnnouncer,
    OkxApiAnnouncer,
    BitgetApiAnnouncer,
)
