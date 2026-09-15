"""Analisis Monte Carlo de la Estrategia 2 optimizada.

Metodo:
  1. Extrae los trades reales del backtest de AMBOS regimenes
     (alcista 2023-24 + bajista 2025-26)
  2. Convierte cada trade en retorno % del capital disponible
  3. Simula 10.000 futuros posibles remuestreando con reemplazo
     (cada simulacion = 52 trades, ~1 ano de operacion)
  4. Reporta distribucion de resultados, drawdowns y prob. de ruina

Uso: python montecarlo.py
"""
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

import config
from data import get_historical_klines
from backtest_strategy2 import run_backtest

N_SIM = 10_000
TRADES_POR_ANO = 52       # frecuencia observada: ~1/semana
NIVELES_RUINA = [0.5, 0.25]  # perder 50% y 75% del capital


def get_trade_returns() -> np.ndarray:
    """Retornos % por trade (PnL / capital en ese momento), de ambos regimenes."""
    returns = []
    for start, end in [("2023-06-01", "2024-09-14"), (None, None)]:
        df = get_historical_klines(
            config.SYMBOL, config.INTERVAL,
            start or "1 year ago UTC", end)
        if start:
            df = df.loc["2023-09-14":]
        r = run_backtest(df)
        capital = config.INITIAL_CAPITAL
        for t in r.trades:
            pnl = (t.exit_price - t.entry_price) * t.quantity
            returns.append(pnl / (capital + pnl))
            capital += pnl
    rets = np.array(returns)
    print(f"Trades historicos usados: {len(rets)} "
          f"(win rate {(rets > 0).mean()*100:.0f}%, "
          f"promedio {rets.mean()*100:+.2f}%)")
    return rets


def simulate(returns: np.ndarray, seed: int = 42):
    rng = np.random.default_rng(seed)
    # matriz: N_SIM caminos x TRADES_POR_ANO pasos, muestreo con reemplazo
    sample = rng.choice(returns, size=(N_SIM, TRADES_POR_ANO), replace=True)
    equity = np.cumprod(1 + sample, axis=1)          # curva de equity relativa
    equity = np.hstack([np.ones((N_SIM, 1)), equity])  # empieza en 1.0

    final = equity[:, -1]
    # max drawdown por camino
    peak = np.maximum.accumulate(equity, axis=1)
    max_dd = ((equity - peak) / peak).min(axis=1)
    return equity, final, max_dd


def report(final, max_dd):
    def pct(x): return f"{x*100:.1f}%"
    print("\n" + "=" * 52)
    print("  RESULTADOS MONTE CARLO (10.000 futuros, 1 ano)")
    print("=" * 52)
    print("  Retorno anual esperado (percentiles):")
    for p in [5, 25, 50, 75, 95]:
        print(f"    P{p:02d}: {(np.percentile(final, p) - 1)*100:+.1f}%")
    print(f"\n  Prob. de terminar el ano en ganancia: {pct((final > 1).mean())}")
    print(f"  Drawdown maximo esperado (mediana):   {pct(np.median(max_dd))}")
    print(f"  Peor drawdown (percentil 95):         {pct(np.percentile(max_dd, 5))}")
    for r in NIVELES_RUINA:
        prob = (final < 1 - r).mean()
        print(f"  Prob. de perder >{int(r*100)}% del capital:    {prob*100:.2f}%")


def plot(equity, final, filename="montecarlo.png"):
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 6))

    # Abanico de trayectorias
    pct_levels = [5, 25, 50, 75, 95]
    qs = np.percentile(equity, pct_levels, axis=0)
    x = np.arange(equity.shape[1])
    ax1.fill_between(x, qs[0], qs[4], alpha=0.2, color="steelblue", label="90% de los casos")
    ax1.fill_between(x, qs[1], qs[3], alpha=0.35, color="steelblue", label="50% de los casos")
    ax1.plot(x, qs[2], color="navy", lw=2, label="Mediana")
    ax1.axhline(1.0, color="gray", ls="--", lw=1)
    for curve in equity[np.random.default_rng(1).choice(len(equity), 60, replace=False)]:
        ax1.plot(x, curve, color="gray", alpha=0.06, lw=0.5)
    ax1.set_title("10.000 futuros posibles (capital inicial = 1.0)")
    ax1.set_xlabel("Trades"); ax1.set_ylabel("Equity relativo")
    ax1.legend()

    # Histograma de resultados anuales
    ax2.hist((final - 1) * 100, bins=80, color="steelblue", edgecolor="white")
    ax2.axvline(0, color="red", lw=2, label="Punto de equilibrio")
    ax2.set_title("Distribucion del retorno anual")
    ax2.set_xlabel("Retorno %"); ax2.set_ylabel("Frecuencia")
    ax2.legend()

    plt.tight_layout()
    plt.savefig(filename, dpi=120)
    print(f"\nGrafico guardado: {filename}")


if __name__ == "__main__":
    returns = get_trade_returns()
    equity, final, max_dd = simulate(returns)
    report(final, max_dd)
    plot(equity, final)
