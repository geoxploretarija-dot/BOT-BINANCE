"""Motor de backtesting con gestion de riesgo y estadisticas.

Simula operaciones con: stop loss, take profit, comisiones y riesgo fijo
por operacion. Genera estadisticas de probabilidad de exito.
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
import config
from strategy import generate_signals

COMMISSION = 0.001  # 0.1% por lado (tasa spot estandar de Binance)


@dataclass
class Trade:
    entry_time: pd.Timestamp
    entry_price: float
    quantity: float
    stop_loss: float
    take_profit: float
    exit_time: pd.Timestamp = None
    exit_price: float = None
    exit_reason: str = ""


@dataclass
class BacktestResult:
    trades: list = field(default_factory=list)
    equity_curve: list = field(default_factory=list)
    final_capital: float = 0.0


def run_backtest(df: pd.DataFrame, initial_capital: float = config.INITIAL_CAPITAL,
                 risk_per_trade: float = config.RISK_PER_TRADE) -> BacktestResult:
    df = generate_signals(df)
    capital = initial_capital
    result = BacktestResult()
    open_trade: Trade | None = None

    for i in range(len(df)):
        row = df.iloc[i]
        price = row["close"]

        # Gestion de posicion abierta: SL / TP
        if open_trade is not None:
            exit_price, reason = None, ""
            if row["low"] <= open_trade.stop_loss:
                exit_price, reason = open_trade.stop_loss, "STOP_LOSS"
            elif row["high"] >= open_trade.take_profit:
                exit_price, reason = open_trade.take_profit, "TAKE_PROFIT"
            elif row["signal"] == -1:
                exit_price, reason = row["close"], "SENAL_VENTA"

            if exit_price is not None:
                pnl = (exit_price - open_trade.entry_price) * open_trade.quantity
                pnl -= (exit_price * open_trade.quantity) * COMMISSION  # comision salida
                capital += pnl
                open_trade.exit_time = df.index[i]
                open_trade.exit_price = exit_price
                open_trade.exit_reason = reason
                result.trades.append(open_trade)
                open_trade = None

        # Apertura de posicion
        if open_trade is None and row["signal"] == 1 and capital > 0:
            stop_loss = price * (1 - config.STOP_LOSS_PCT)
            take_profit = price * (1 + config.TAKE_PROFIT_PCT)
            risk_amount = capital * risk_per_trade
            # Tamano de posicion segun distancia al stop loss
            quantity = risk_amount / (price - stop_loss)
            cost = quantity * price * (1 + COMMISSION)
            if cost > capital:
                quantity = capital / (price * (1 + COMMISSION))
            capital -= quantity * price * COMMISSION  # comision entrada
            open_trade = Trade(df.index[i], price, quantity, stop_loss, take_profit)

        # Curva de equity (mark-to-market)
        equity = capital + (open_trade.quantity * price if open_trade else 0)
        result.equity_curve.append({"time": df.index[i], "equity": equity})

    # Cerrar posicion abierta al final
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


def compute_stats(result: BacktestResult, initial_capital: float = config.INITIAL_CAPITAL) -> dict:
    """Estadisticas de rendimiento y probabilidad de exito."""
    trades = result.trades
    if not trades:
        return {"error": "Sin operaciones"}

    pnls = np.array([(t.exit_price - t.entry_price) * t.quantity for t in trades])
    wins = pnls[pnls > 0]
    losses = pnls[pnls <= 0]

    equity = pd.Series([e["equity"] for e in result.equity_curve],
                       index=[e["time"] for e in result.equity_curve])
    peak = equity.cummax()
    max_drawdown = ((equity - peak) / peak).min()

    gross_profit = wins.sum() if len(wins) else 0
    gross_loss = abs(losses.sum()) if len(losses) else 0

    # Intervalo de confianza del win rate (Wilson 95%)
    n = len(trades)
    p = len(wins) / n
    z = 1.96
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = z * np.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom

    return {
        "capital_inicial": round(initial_capital, 2),
        "capital_final": round(result.final_capital, 2),
        "retorno_%": round((result.final_capital / initial_capital - 1) * 100, 2),
        "total_trades": n,
        "ganadoras": len(wins),
        "perdedoras": len(losses),
        "win_rate_%": round(p * 100, 2),
        "win_rate_IC95%": [round((center - margin) * 100, 1), round((center + margin) * 100, 1)],
        "profit_factor": round(gross_profit / gross_loss, 2) if gross_loss > 0 else float("inf"),
        "ganancia_promedio": round(wins.mean(), 2) if len(wins) else 0,
        "perdida_promedio": round(losses.mean(), 2) if len(losses) else 0,
        "max_drawdown_%": round(max_drawdown * 100, 2),
        "mejor_trade": round(pnls.max(), 2),
        "peor_trade": round(pnls.min(), 2),
    }


def print_report(result: BacktestResult, stats: dict):
    print("=" * 55)
    print("  REPORTE DE BACKTEST")
    print("=" * 55)
    for k, v in stats.items():
        print(f"  {k:20}: {v}")
    print("=" * 55)
    print("\nUltimas 10 operaciones:")
    for t in result.trades[-10:]:
        pnl = (t.exit_price - t.entry_price) * t.quantity
        icon = "WIN " if pnl > 0 else "LOSS"
        print(f"  [{icon}] {str(t.entry_time)[:16]} -> {str(t.exit_time)[:16]}"
              f"  ${t.entry_price:.0f} -> ${t.exit_price:.0f}"
              f"  PnL: ${pnl:+.2f} ({t.exit_reason})")


if __name__ == "__main__":
    from data import get_historical_klines

    print(f"Descargando datos de {config.SYMBOL} ({config.INTERVAL})...")
    df = get_historical_klines(config.SYMBOL, config.INTERVAL, "1 year ago UTC")
    print(f"{len(df)} velas descargadas.\n")

    result = run_backtest(df)
    stats = compute_stats(result)
    print_report(result, stats)

    pd.DataFrame(result.equity_curve).to_csv("equity_curve.csv", index=False)
    print("\nCurva de equity guardada en equity_curve.csv")
