import httpx
from .symbol import Symbol

async def get_new_symbols():
    spot_url = "https://api.bybit.com/v5/market/instruments-info?category=spot"
    futures_url = "https://api.bybit.com/v5/market/instruments-info?category=linear"

    async with httpx.AsyncClient() as client:
        spot_resp = await client.get(spot_url)
        futures_resp = await client.get(futures_url)

    spot_data = spot_resp.json().get("result", {}).get("list", [])
    futures_data = futures_resp.json().get("result", {}).get("list", [])

    spot_symbols = {s["symbol"] for s in spot_data}
    futures_symbols = {s["symbol"] for s in futures_data}

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
