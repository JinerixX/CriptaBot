class Symbol:
    def __init__(self, name: str, market_type: str):
        self.name = name
        self.market_type = market_type  # Spot, Futures или Both
