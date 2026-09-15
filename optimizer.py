"""Optimizador de parametros: prueba combinaciones de SMA/SL/TP
y reporta las mejores segun retorno con win rate validado.

ADVERTENCIA: resultados sobre datos pasados pueden estar sobreajustados.
Por eso el flujo completo incluye paper trading para validar.
"""
import itertools
import pandas as pd
import config
from data import get_historical_klines
from backtest import run_backtest, compute_stats

GRID = {
    "SMA_FAST": [10, 20, 30],
    "SMA_SLOW": [50, 100, 200],
    "STOP_LOSS_PCT": [0.015, 0.02, 0.03],
    "TAKE_PROFIT_PCT": [0.03, 0.04, 0.06],
}


def main():
    df = get_historical_klines(config.SYMBOL, config.INTERVAL, "1 year ago UTC")
    results = []

    combos = [c for c in itertools.product(*GRID.values())]
    print(f"Probando {len(combos)} combinaciones...")

    for combo in combos:
        params = dict(zip(GRID.keys(), combo))
        if params["SMA_FAST"] >= params["SMA_SLOW"]:
            continue
        config.SMA_FAST = params["SMA_FAST"]
        config.SMA_SLOW = params["SMA_SLOW"]
        config.STOP_LOSS_PCT = params["STOP_LOSS_PCT"]
        config.TAKE_PROFIT_PCT = params["TAKE_PROFIT_PCT"]

        r = run_backtest(df)
        s = compute_stats(r)
        if "error" in s or s["total_trades"] < 15:
            continue
        results.append({**params, **{k: s[k] for k in [
            "retorno_%", "total_trades", "win_rate_%",
            "profit_factor", "max_drawdown_%"]}})

    df_res = pd.DataFrame(results).sort_values("retorno_%", ascending=False)
    top = df_res.head(10)
    print("\nTOP 10 configuraciones:")
    print(top.to_string(index=False))
    df_res.to_csv("optimization_results.csv", index=False)
    print("\nResultados completos en optimization_results.csv")


if __name__ == "__main__":
    main()
