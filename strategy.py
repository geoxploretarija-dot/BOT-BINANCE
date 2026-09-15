"""Estrategia: cruce de medias moviles + filtro RSI.

Senal de COMPRA:
  - SMA rapida cruza por encima de la SMA lenta (cruce dorado)
  - RSI < sobrecompra (evitamos entrar en techo)

Senal de VENTA:
  - SMA rapida cruza por debajo de la SMA lenta (cruce de la muerte)
  - O stop loss / take profit (gestionado por el motor de backtest)
"""
import pandas as pd
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
import config


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["sma_fast"] = SMAIndicator(df["close"], window=config.SMA_FAST).sma_indicator()
    df["sma_slow"] = SMAIndicator(df["close"], window=config.SMA_SLOW).sma_indicator()
    df["rsi"] = RSIIndicator(df["close"], window=config.RSI_PERIOD).rsi()
    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Agrega columnas 'signal' (1=compra, -1=venta, 0=nada)."""
    df = add_indicators(df)
    df["signal"] = 0

    prev_fast = df["sma_fast"].shift(1)
    prev_slow = df["sma_slow"].shift(1)

    cross_up = (df["sma_fast"] > df["sma_slow"]) & (prev_fast <= prev_slow)
    cross_down = (df["sma_fast"] < df["sma_slow"]) & (prev_fast >= prev_slow)

    df.loc[cross_up & (df["rsi"] < config.RSI_OVERBOUGHT), "signal"] = 1
    df.loc[cross_down, "signal"] = -1
    return df
