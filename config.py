"""Configuracion central del bot."""
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY", "")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY", "")
USE_TESTNET = os.getenv("USE_TESTNET", "true").lower() == "true"

# Parametros de trading
SYMBOL = "BTCUSDT"
INTERVAL = "1h"          # velas de 1 hora
INITIAL_CAPITAL = 10_000  # USD simulados
RISK_PER_TRADE = 0.02    # 2% del capital por operacion
STOP_LOSS_PCT = 0.02     # 2%
TAKE_PROFIT_PCT = 0.04   # 4%

# Parametros de la estrategia
SMA_FAST = 20
SMA_SLOW = 50
RSI_PERIOD = 14
RSI_OVERSOLD = 30
RSI_OVERBOUGHT = 70
