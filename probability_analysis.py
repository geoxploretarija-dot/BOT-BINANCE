"""Estudio estadistico: que tan frecuentes son los pullbacks en tendencia
alcista, y cuanto tardan en llegar desde niveles de RSI altos.

Responde: 'si el mercado esta alcista y RSI alto, cual es la probabilidad
y esperanza de tiempo para que llegue un pullback RSI(6)<30?'
"""
import pandas as pd
import numpy as np
import config
from data import get_historical_klines
from strategy2 import add_indicators, RSI_BUY

df = get_historical_klines(config.SYMBOL, config.INTERVAL, "2023-01-01", None)
d = add_indicators(df)
slope_up = d["ema200"] > d["ema200"].shift(10)
in_trend = (d["close"] > d["ema200"]) & slope_up

n_trend = int(in_trend.sum())
n_pullback = int((in_trend & (d["rsi"] < RSI_BUY)).sum())
print(f"Datos: {d.index[0]:%Y-%m-%d} -> {d.index[-1]:%Y-%m-%d} ({len(d)} velas de 1h)")
print(f"\n1) Velas en tendencia alcista:      {n_trend} ({n_trend/len(d)*100:.0f}%)")
print(f"2) Velas en tendencia CON pullback: {n_pullback} ({n_pullback/n_trend*100:.1f}% de las velas en tendencia)")

# Espera tipica: desde vela con RSI>70 en tendencia hasta proximo RSI<30
high = in_trend & (d["rsi"] > 70)
waits = []
idx = d.index.to_series()
rsi = d["rsi"].values
trend = in_trend.values
positions = np.where(high.values)[0]
for p in positions[::24]:  # muestrea 1 vez al dia para no solapar rachas
    for j in range(p + 1, min(p + 30 * 24, len(rsi))):  # ventana 30 dias
        if trend[j] and rsi[j] < RSI_BUY:
            waits.append(j - p)
            break

waits = np.array(waits)
print(f"\n3) Desde un momento como HOY (RSI>70 en tendencia):")
print(f"   Casos historicos analizados: {len(waits)}")
print(f"   Prob. de pullback en <24h : {(waits < 24).mean()*100:.0f}%")
print(f"   Prob. de pullback en <3d  : {(waits < 72).mean()*100:.0f}%")
print(f"   Prob. de pullback en <7d  : {(waits < 168).mean()*100:.0f}%")
print(f"   Prob. de pullback en <14d : {(waits < 336).mean()*100:.0f}%")
if len(waits):
    print(f"   Tiempo mediano de espera  : {np.median(waits)/24:.1f} dias")
