import httpx
from .symbol import Symbol


def _clean(ticker: str) -> str:
    """убираем всё после '_' и дефисы."""
    return ticker.split("_", 1)[0].replace("-", "")


async def get_new_symbols():
    spot_url = "https://api.bitget.com/api/spot/v1/public/products"
    fut_url  = "https://api.bitget.com/api/mix/v1/market/contracts?productType=umcbl"

    async with httpx.AsyncClient() as client:
        spot_r, fut_r = await client.get(spot_url), await client.get(fut_url)

    spot = {_clean(s["symbol"]) for s in spot_r.json().get("data", [])}
    fut  = {_clean(s["symbol"]) for s in fut_r.json().get("data", [])}

    symbols = []

    for sym in spot | fut:
        if sym in spot and sym in fut:
            mkt = "Both"
        elif sym in spot:
            mkt = "Spot"
        else:
            mkt = "Futures"
        symbols.append(Symbol(sym, mkt))

    return symbols
