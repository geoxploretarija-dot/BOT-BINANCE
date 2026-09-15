# 🤖 Bot de Trading Binance — Tendencia + Pullback

Sistema de trading algorítmico con validación estadística rigurosa, operando
en **Binance Spot Testnet** (dinero simulado) 24/7 desde la nube, con
reportes en vivo por Telegram.

**Costo total de infraestructura: $0/mes.**

## Estrategia validada (E2)

| Regla | Detalle |
|---|---|
| **Entrada** | Precio > EMA200 (con pendiente positiva) + RSI(6) < 30 (pullback) |
| **Salida** | Trailing stop a 4×ATR (las ganancias corren) |
| **Riesgo** | 2% del capital por trade, exposición máxima 25% |
| **Mercado** | BTCUSDT spot, velas de 1h, solo largo |

### Validación estadística realizada

- ✅ Backtest en **2 regímenes** (alcista 2023-24: +10.1% | bajista 2025-26: +0.1%)
- ✅ Optimización robusta (maximina el peor caso, maximiza robustez)
- ✅ **Monte Carlo: 10,000 trayectorias** → 85% probabilidad de terminar el año en positivo, drawdown mediano -2.9%
- ✅ Otras monedas probadas y **rechazadas con datos**: ETH ❌, SOL ❌, BNB ⚠️ (empate técnico), ADA ❌
- 🔄 **En curso:** 4+ semanas de paper trading en vivo antes de evaluar dinero real

## Infraestructura

```
Render (Frankfurt) — server.py (Flask + bot loop)
        │
UptimeRobot (ping 5 min, anti-sleep del tier free)
        │
Telegram Bot — /status  /resumen  /mercado  + alertas automáticas de trades
        │
GitHub Actions — monitor de salud cada 2h, resumen estadístico cada 2 días
        │
GitHub — repositorio del código + PERSISTENCIA de estado (posiciones,
         trades, chat_id sobreviven redespliegues; trailing stop se
         recupera recalculando desde datos de mercado)
```

## Comandos locales

```powershell
.\venv\Scripts\python.exe backtest_strategy2.py   # backtest
.\venv\Scripts\python.exe montecarlo.py           # simulación Monte Carlo
.\venv\Scripts\python.exe market_analysis.py      # análisis técnico ahora
.\venv\Scripts\python.exe paper_trader.py --status # estado del bot local
```

## Roadmap del proyecto

| Fase | Estado |
|---|---|
| Backtesting + optimización de la estrategia | ✅ Completado |
| Monte Carlo — validación estadística | ✅ Completado |
| Paper trading 24/7 en nube (Render) | ✅ Corriendo |
| Alertas Telegram + monitoreo automatizado | ✅ Completado |
| Persistencia / tolerancia a fallos | ✅ Completado |
| **Validación en vivo 4+ semanas (>30 trades)** | 🔄 En curso |
| Paso a cuenta real ($11, exposición ajustada) | ⏳ Solo si valida |
| Multi-activo (altcoins re-validadas por régimen) | ⏳ Futuro |
| Futuros (apalancamiento controlado 1-2x) | ⏳ Futuro |
| Régimen adaptativo por volatilidad (BB width / HMM) | ⏳ Fase avanzada |
| ML para probabilidad de éxito por señal (López de Prado) | ⏳ Fase avanzada |

## 📚 Biblioteca de formación (plan de estudio)

Perfil: ingeniero civil con maestría en hidráulica → ventaja natural en
turbulencia/estocástica/econofísica.

### Nivel 1 — Probabilidad y estadística (meses 1-3)
- [ ] **Introduction to Probability** — Blitzstein & Hwang (gratis, online)
- [ ] **The Elements of Statistical Learning** — Hastie, Tibshirani, Friedman

### Nivel 2 — Series de tiempo (meses 2-4)
- [ ] **Forecasting: Principles and Practice** — Hyndman & Athanasopoulos (gratis online)
- [ ] **Analysis of Financial Time Series** — Ruey Tsay

### Nivel 3 — Trading algorítmico (el manual del bot)
- [ ] **Algorithmic Trading** — Ernest P. Chan ⭐ (leer primero)
- [ ] **Quantitative Technical Analysis** — Howard Bandy
- [ ] **Advances in Financial Machine Learning** — Marcos López de Prado

### Nivel 4 — Econofísica (nicho natural del perfil hidráulico)
- [ ] **An Introduction to Econophysics** — Mantegna & Stanley
- [ ] **Critical Phenomena in Natural Sciences** — Didier Sornette
- [ ] **The (Mis)behavior of Markets** — Benoît Mandelbrot

### Complementario
- [ ] **Python for Finance** — Yves Hilpisch

## ⚠️ Disclaimer

Proyecto educativo de investigación. El paper trading actual corre con
dinero simulado. Nada de esto constituye asesoría financiera. Los
resultados del pasado (incluso bien validados) no garantizan resultados
futuros.
