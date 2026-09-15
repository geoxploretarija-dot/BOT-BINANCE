"""Analisis del estado actual del mercado vs criterios de la Estrategia 2."""
import config
from data import get_historical_klines
from strategy2 import add_indicators, RSI_BUY

df = get_historical_klines(config.SYMBOL, config.INTERVAL, "3 months ago UTC")
d = add_indicators(df)

last = d.iloc[-1]
prev = d.iloc[-2]
slope_up = last["ema200"] > d["ema200"].iloc[-11]  # pendiente (10 velas)

dist = (last["close"] / last["ema200"] - 1) * 100
slope_pct = (last["ema200"] / d["ema200"].iloc[-11] - 1) * 100

print(f"=== ANALISIS {config.SYMBOL} | vela {d.index[-1]} ===")
print(f"Precio actual : ${last['close']:,.0f}")
print(f"EMA 200       : ${last['ema200']:,.0f}  ({dist:+.1f}%)")
print(f"Pendiente EMA : {slope_pct:+.2f}% (ultimas 10 velas)")
print(f"RSI(6) actual : {last['rsi']:.1f}")

# 1) Filtros de la estrategia
cond1 = last["close"] > last["ema200"]
cond3 = last["rsi"] < RSI_BUY
print()
print(f"1. Precio sobre EMA200      : {'SI' if cond1 else 'NO'}")
print(f"2. EMA200 pendiente positiva: {'SI' if slope_up else 'NO'}")
print(f"3. RSI < {RSI_BUY} (pullback)    : {'SI' if cond3 else 'NO'}")
print(f"==> SENAL DE COMPRA: {'SI' if (cond1 and slope_up and cond3) else 'NO (esperando)'}")

# 2) Clima general: ultimos 30 dias
window = d.iloc[-30*24:]
up_days = (window["close"].diff() > 0).mean() * 100
ret_30d = (last["close"] / d["close"].iloc[-30*24] - 1) * 100
print(f"\n--- Contexto ultimos 30 dias ---")
print(f"Retorno: {ret_30d:+.1f}% | Velas verdes: {up_days:.0f}%")

# 3) Que falta para la entrada
print("\n--- Que falta para entrar ---")
if not cond1:
    print(f"- Precio debe superar EMA200: +${last['ema200']-last['close']:,.0f} mas ({-dist:.1f}%)")
if not slope_up:
    print("- EMA200 debe dar la vuelta al alza (semana(s) de precio sostenido arriba)")
if cond1 and slope_up and not cond3:
    print(f"- RSI debe bajar de {RSI_BUY} (retroceso dentro de la tendencia)")
