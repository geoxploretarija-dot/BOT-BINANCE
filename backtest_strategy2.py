"""Backtest de la Estrategia 2 (Tendencia + Pullback) con 3 mejoras:

  1. Trailing stop 4xATR (deja correr ganancias en vez de salir pronto)
  2. Exposicion maxima 25% del capital por trade (controla el drawdown)
  3. Filtro: EMA200 con pendiente positiva (en strategy2.generate_signals)

La salida es SOLO por stop loss / trailing stop (las ganancias corren).
"""
import pandas as pd
import numpy as np

import config
from data import get_historical_klines
from strategy2 import generate_signals, ATR_STOP_MULT
from backtest import Trade, BacktestResult, compute_stats, print_report, COMMISSION

MAX_EXPOSURE = 0.25  # Mejora 2: maximo 25% del capital por trade


def run_backtest(df: pd.DataFrame, initial_capital: float = config.INITIAL_CAPITAL,
                 risk_per_trade: float = config.RISK_PER_TRADE) -> BacktestResult:
    df = generate_signals(df)
    capital = initial_capital
    result = BacktestResult()
    open_trade: Trade | None = None
    highest_close = 0.0

    for i in range(len(df)):
        row = df.iloc[i]
        price = row["close"]
        atr = row["atr"] if not np.isnan(row["atr"]) else price * 0.01

        if open_trade is not None:
            # Mejora 1: trailing stop -> el stop sube con el precio, nunca baja
            highest_close = max(highest_close, price)
            trail_stop = highest_close - ATR_STOP_MULT * atr
            open_trade.stop_loss = max(open_trade.stop_loss, trail_stop)

            if row["low"] <= open_trade.stop_loss:
                exit_price = open_trade.stop_loss
                reason = "TRAILING_STOP" if open_trade.stop_loss > open_trade.entry_price else "STOP_LOSS"
                pnl = (exit_price - open_trade.entry_price) * open_trade.quantity
                pnl -= (exit_price * open_trade.quantity) * COMMISSION
                capital += pnl
                open_trade.exit_time = df.index[i]
                open_trade.exit_price = exit_price
                open_trade.exit_reason = reason
                result.trades.append(open_trade)
                open_trade = None

        if open_trade is None and row["signal"] == 1 and capital > 0:
            stop_loss = price - ATR_STOP_MULT * atr
            risk_amount = capital * risk_per_trade
            quantity = risk_amount / (price - stop_loss)
            # Mejora 2: limitar exposicion al 25% del capital disponible
            quantity = min(quantity, (capital * MAX_EXPOSURE) / price)
            capital -= quantity * price * COMMISSION
            open_trade = Trade(df.index[i], price, quantity, stop_loss,
                               float("inf"))
            highest_close = price

        equity = capital + (open_trade.quantity * price if open_trade else 0)
        result.equity_curve.append({"time": df.index[i], "equity": equity})

    if open_trade is not None:
        last_price = df.iloc[-1]["close"]
        pnl = (last_price - open_trade.entry_price) * open_trade.quantity
        pnl -= (last_price * open_trade.quantity) * COMMISSION
        capital += pnl
        open_trade.exit_time = df.index[-1]
        open_trade.exit_price = last_price
        open_trade.exit_reason = "FIN_DATOS"
        result.trades.append(open_trade)

    result.final_capital = capital
    return result


if __name__ == "__main__":
    print(f"Descargando datos de {config.SYMBOL} ({config.INTERVAL})...")
    df = get_historical_klines(config.SYMBOL, config.INTERVAL, "1 year ago UTC")
    print(f"{len(df)} velas.\n")
    print("ESTRATEGIA 2: Tendencia(EMA200 pend+) + RSI(6)<30 + Trail 4xATR")
    result = run_backtest(df)
    stats = compute_stats(result)
    print_report(result, stats)
