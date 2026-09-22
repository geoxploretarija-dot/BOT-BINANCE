"""Configuracion central del bot."""
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY", "")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() == "true"

# Parametros de trading (activos)
SYMBOL = "BTCUSDT"
INTERVAL = "1h"          # velas de 1 hora
INITIAL_CAPITAL = 10_000  # USD simulados
RISK_PER_TRADE = 0.02    # 2% del capital por operacion
# NOTA: riesgo nominal 2%, pero el sizing limita por exposicion maxima
# (25% del capital): el riesgo EFECTIVO ronda 0.4-0.6% con ATR tipico.

# Parametros de la ESTRATEGIA 1 (SMA cross, descartada por backtest).
# El bot en vivo usa strategy2.py (EMA200 + RSI6 + trailing ATR) y NO
# los lee; se conservan solo para backtest.py / strategy.py / optimizer.py.
SMA_FAST = 20
SMA_SLOW = 50
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
STOP_LOSS_PCT = 0.02     # 2%
TAKE_PROFIT_PCT = 0.04   # 4%
