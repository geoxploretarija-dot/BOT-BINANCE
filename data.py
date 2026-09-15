"""Descarga de datos historicos de velas (klines)."""
import pandas as pd
from binance.client import Client
from client import get_client


def get_historical_klines(symbol: str, interval: str,
                          start_str: str = "1 year ago UTC",
                          end_str: str = None) -> pd.DataFrame:
    """Descarga klines historicos. No requiere API key (datos publicos)."""
    client = Client()  # datos publicos, sin autenticacion
    klines = client.get_historical_klines(symbol, interval, start_str, end_str)
    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    df["close_time"] = pd.to_datetime(df["close_time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = df[col].astype(float)
    df.set_index("open_time", inplace=True)
    return df


if __name__ == "__main__":
    import config
    df = get_historical_klines(config.SYMBOL, config.INTERVAL)
    print(df.tail())
    print(f"\nTotal velas: {len(df)}")
    df.to_csv(f"data_{config.SYMBOL}_{config.INTERVAL}.csv")
