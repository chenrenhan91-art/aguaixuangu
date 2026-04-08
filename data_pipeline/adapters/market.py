from datetime import date, timedelta

from data_pipeline.adapters.base import BaseAdapter


class DemoMarketDataAdapter(BaseAdapter[list[dict[str, object]]]):
    def __init__(self, symbols: list[str], lookback_days: int = 40) -> None:
        self.symbols = symbols
        self.lookback_days = lookback_days

    def fetch(self) -> list[dict[str, object]]:
        rows: list[dict[str, object]] = []
        start = date.today() - timedelta(days=self.lookback_days)

        for symbol_index, symbol in enumerate(self.symbols):
            base_close = 32.0 + symbol_index * 18.0
            for offset in range(self.lookback_days):
                trade_date = start + timedelta(days=offset)
                if trade_date.weekday() >= 5:
                    continue

                drift = offset * (0.18 + symbol_index * 0.01)
                seasonal = ((offset % 5) - 2) * 0.22
                close = round(base_close + drift + seasonal, 2)
                open_price = round(close - 0.35, 2)
                high = round(close + 0.66, 2)
                low = round(close - 0.72, 2)
                amount = round((1.2 + symbol_index * 0.15 + offset * 0.01) * 1_000_000, 2)

                rows.append(
                    {
                        "trade_date": trade_date.isoformat(),
                        "symbol": symbol,
                        "open": open_price,
                        "high": high,
                        "low": low,
                        "close": close,
                        "amount": amount,
                    }
                )

        return rows

