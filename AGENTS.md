# AGENTS.md — Guía para agentes de código (Bot Binance)

## ¿Qué es este proyecto?

Bot de trading algorítmico para Binance (spot, solo largo) operando en
**Testnet** (dinero simulado). Desplegado 24/7 en Render (Frankfurt),
con reportes por Telegram y monitoreo vía GitHub Actions.

**Estado: en fase de VALIDACIÓN EN VIVO con dinero simulado.**
No mover a cuenta real hasta completar 4+ semanas de paper trading.

## Arquitectura

```
Binance Testnet ←→ Render (server.py: Flask + loop en hilo)
                        ├── paper_trader.py   (lógica de ejecución)
                        ├── strategy2.py      (señales de trading)
                        ├── storage.py        (persistencia en GitHub)
                        └── telegram_bot.py   (comandos + alertas)
GitHub Actions: monitor cada 2h, resumen cada 2 días
UptimeRobot: ping cada 5 min (evita sleep del tier free)
```

## Archivos clave

| Archivo | Rol |
|---|---|
| `config.py` | Parámetros globales (símbolo, riesgo, indicadores) |
| `strategy2.py` | Estrategia validada: EMA200 pendiente+ / RSI(6)<30 / trailing 4×ATR |
| `strategy.py` | Estrategia 1 (SMA cross) — descartada por backtest |
| `paper_trader.py` | Motor de ejecución en vivo (testnet) |
| `backtest_strategy2.py` | Backtest de la estrategia validada |
| `optimizer2.py` | Optimización robusta (2 regímenes a la vez) |
| `montecarlo.py` | Simulación Monte Carlo (10k trayectorias) |
| `storage.py` | Persistencia de estado en GitHub Contents API |
| `server.py` | Servidor Flask + loop del bot (endpoints / /status /report) |

## Reglas que NO se negocian

1. **Nunca** operar cuenta real sin autorización explícita después de
   validación estadística completa.
2. `USE_TESTNET=true` por defecto siempre.
3. Las claves van en `.env` (local) o env vars (Render). NUNCA en código.
4. El `.env` está en `.gitignore` — verificar antes de cada commit.
5. Riesgo por trade: 2% | Exposición máxima: 25% | Nunca apalancamiento.
6. Toda estrategia nueva pasa el protocolo: backtest → optimización
   robusta (alcista+bajista) → Monte Carlo → paper trading 4 semanas.

## Cómo correr localmente

```powershell
python -m venv venv; .\venv\Scripts\pip install -r requirements.txt
.\venv\Scripts\python.exe backtest_strategy2.py     # backtest
.\venv\Scripts\python.exe montecarlo.py             # Monte Carlo
.\venv\Scripts\python.exe paper_trader.py --status  # estado local
.\venv\Scripts\python.exe server.py                 # servidor + bot
```

## Deploy

Push a `main` → Render auto-redeploy. Secrets en Render:
`BINANCE_API_KEY`, `BINANCE_SECRET_KEY`, `USE_TESTNET`,
`TELEGRAM_TOKEN`, `GITHUB_TOKEN`, `GITHUB_REPO`.

Secrets en GitHub (Actions): `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`.

## Convenciones

- Español en comentarios y docstrings.
- Estilo simple explícito; sin frameworks pesados.
- Cambios mínimos; probar antes de pushear a main (Render autodeploy).
- Commits descriptivos en español.
