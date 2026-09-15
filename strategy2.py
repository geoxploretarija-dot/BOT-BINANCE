"""Estrategia 2: Tendencia + Pullback (mean reversion en tendencia).

Reglas:
  - Solo largo si precio > EMA200 (tendencia alcista confirmada)
  - Entrada: RSI(6) < 25 (retroceso/sobreventa dentro de la tendencia)
  - Salida: RSI(6) > 55 o stop de 2x ATR
"""
import pandas as pd
from ta.trend import EMAIndicator
from ta.volatility import AverageTrueRange
from ta.momentum import RSIIndicator

EMA_TREND = 200
RSI_FAST = 6
RSI_BUY = 30
RSI_SELL = 55
ATR_PERIOD = 14
ATR_STOP_MULT = 4.0


def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["ema200"] = EMAIndicator(df["close"], window=EMA_TREND).ema_indicator()
    df["rsi"] = RSIIndicator(df["close"], window=RSI_FAST).rsi()
    df["atr"] = AverageTrueRange(df["high"], df["low"], df["close"],
                                 window=ATR_PERIOD).average_true_range()
    return df


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    df = add_indicators(df)
    df["signal"] = 0
    # Mejora 3: la EMA200 debe tener PENDIENTE POSITIVA (tendencia fortaleciendose)
    ema_slope_up = df["ema200"] > df["ema200"].shift(10)
    in_trend = (df["close"] > df["ema200"]) & ema_slope_up
    df.loc[in_trend & (df["rsi"] < RSI_BUY), "signal"] = 1
    df.loc[df["rsi"] > RSI_SELL, "signal"] = -1
    return df
