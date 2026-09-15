"""Optimizacion robusta: busca parametros que funcionen en AMBOS regimenes
(alcista 2023-24 y bajista/lateral 2025-26) simultaneamente."""
import itertools
import pandas as pd

import config
import strategy2
import backtest_strategy2 as bs2
from data import get_historical_klines
from backtest import compute_stats

GRID = {
    "RSI_BUY": [20, 25, 30],
    "ATR_STOP_MULT": [2.0, 3.0, 4.0],
}


def main():
    print("Descargando ambos periodos...")
    df_bear = get_historical_klines(config.SYMBOL, config.INTERVAL, "1 year ago UTC")
    df_bull = get_historical_klines(config.SYMBOL, config.INTERVAL,
                                    "2023-06-01", "2024-09-14").loc["2023-09-14":]
    rows = []
    for rsi_buy, atr_mult in itertools.product(GRID["RSI_BUY"], GRID["ATR_STOP_MULT"]):
        strategy2.RSI_BUY = rsi_buy
        bs2.ATR_STOP_MULT = atr_mult

        s_bear = compute_stats(bs2.run_backtest(df_bear))
        s_bull = compute_stats(bs2.run_backtest(df_bull))
        if "error" in s_bear or "error" in s_bull:
            continue
        score = min(s_bear["retorno_%"], s_bull["retorno_%"])  # peor caso
        rows.append({
            "RSI_BUY": rsi_buy, "ATR_MULT": atr_mult,
            "ret_bajista_%": s_bear["retorno_%"], "dd_bajista_%": s_bear["max_drawdown_%"],
            "ret_alcista_%": s_bull["retorno_%"], "dd_alcista_%": s_bull["max_drawdown_%"],
            "peor_caso_%": score,
        })
        print(f"  RSI<{rsi_buy:>2} ATRx{atr_mult}: bajista {s_bear['retorno_%']:+.1f}% "
              f"| alcista {s_bull['retorno_%']:+.1f}% | peor caso {score:+.1f}%")

    res = pd.DataFrame(rows).sort_values("peor_caso_%", ascending=False)
    print("\nRanking por robustez (maximiza el peor caso):")
    print(res.to_string(index=False))
    res.to_csv("robust_optimization.csv", index=False)


if __name__ == "__main__":
    main()
