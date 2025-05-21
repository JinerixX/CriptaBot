import httpx
from .symbol import Symbol

async def get_new_symbols():
    spot_url = "https://api.binance.com/api/v3/exchangeInfo"
    futures_url = "https://fapi.binance.com/fapi/v1/exchangeInfo"

    async with httpx.AsyncClient() as client:
        spot_resp, fut_resp = await client.get(spot_url), await client.get(futures_url)

    spot_symbols = {s["symbol"] for s in spot_resp.json().get("symbols", [])}
    futures_symbols = {s["symbol"] for s in fut_resp.json().get("symbols", [])}

    all_symbols = spot_symbols | futures_symbols
    result = []

    for symbol in all_symbols:
        if symbol in spot_symbols and symbol in futures_symbols:
            result.append(Symbol(symbol, "Both"))
        elif symbol in spot_symbols:
            result.append(Symbol(symbol, "Spot"))
        else:
            result.append(Symbol(symbol, "Futures"))

    return result
