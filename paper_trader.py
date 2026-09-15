"""Paper trading en Binance Testnet - Estrategia 2 (Tendencia + Pullback).

Parametros optimizados (validados en mercado alcista Y bajista):
  - Entrada: precio > EMA200 (pendiente positiva) y RSI(6) < 30
  - Salida: trailing stop de 4x ATR (las ganancias corren)
  - Exposicion maxima: 25% del capital por trade
  - Riesgo: 2% del capital por trade

Uso:  python paper_trader.py            (modo continuo)
      python paper_trader.py --once     (un solo ciclo, para probar)
      python paper_trader.py --status   (ver estado actual)

Detener: Ctrl+C
"""
import sys
import json
import time
import math
import argparse
from datetime import datetime, timezone

import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
from client import get_client
from strategy2 import generate_signals, ATR_STOP_MULT
import telegram_bot

STATE_FILE = "paper_state2.json"
LOG_FILE = "paper_trades2.csv"
CHECK_INTERVAL = 60  # segundos entre chequeos de precio
MAX_EXPOSURE = 0.25  # 25% del capital maximo por trade


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_state() -> dict:
    try:
        with open(STATE_FILE) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"position": None, "processed_candles": []}


def save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def record_trade(row: dict):
    import os
    df = pd.DataFrame([row])
    df.to_csv(LOG_FILE, mode="a", index=False, header=not os.path.exists(LOG_FILE))


def get_recent_klines(client, limit=250) -> pd.DataFrame:
    klines = client.get_klines(symbol=config.SYMBOL,
                               interval=config.INTERVAL, limit=limit)
    df = pd.DataFrame(klines, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    for col in ["open", "high", "low", "close"]:
        df[col] = df[col].astype(float)
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    return df


def round_step(client, symbol: str, quantity: float) -> float:
    info = client.get_symbol_info(symbol)
    for f in info["filters"]:
        if f["filterType"] == "LOT_SIZE":
            step = float(f["stepSize"])
            return math.floor(quantity / step) * step
    return quantity


def open_position(client, state, price: float, atr: float, candle_time: str):
    balance = float(client.get_asset_balance("USDT")["free"])
    stop_loss = price - ATR_STOP_MULT * atr

    risk_amount = balance * config.RISK_PER_TRADE
    quantity = risk_amount / (price - stop_loss)
    quantity = min(quantity, (balance * MAX_EXPOSURE) / price)
    quantity = round_step(client, config.SYMBOL, quantity)
    if quantity <= 0:
        log("Cantidad calculada demasiado pequena. No se abre posicion.")
        return

    order = client.order_market_buy(symbol=config.SYMBOL, quantity=quantity)
    fill_price = float(order["fills"][0]["price"]) if order.get("fills") else price
    log(f"COMPRA {quantity} {config.SYMBOL} @ {fill_price:.2f} | "
        f"SL inicial={stop_loss:.2f} (4xATR)")
    telegram_bot.send(f"🟢 COMPRA {config.SYMBOL}\n"
                      f"Precio: ${fill_price:.2f}\nCantidad: {quantity}\n"
                      f"SL inicial: ${stop_loss:.2f} (4xATR)")

    state["position"] = {
        "entry_time": str(candle_time),
        "entry_price": fill_price,
        "quantity": quantity,
        "stop_loss": stop_loss,
        "highest_close": fill_price,
    }
    save_state(state)


def close_position(client, state, price: float, reason: str):
    pos = state["position"]
    if pos is None:
        return
    quantity = round_step(client, config.SYMBOL, pos["quantity"])
    order = client.order_market_sell(symbol=config.SYMBOL, quantity=quantity)
    fill_price = float(order["fills"][0]["price"]) if order.get("fills") else price
    pnl = (fill_price - pos["entry_price"]) * pos["quantity"]
    log(f"VENTA {quantity} {config.SYMBOL} @ {fill_price:.2f} | "
        f"PnL: ${pnl:+.2f} ({reason})")
    emoji = "🟢" if pnl > 0 else "🔴"
    telegram_bot.send(f"{emoji} VENTA {config.SYMBOL} ({reason})\n"
                      f"Entrada: ${pos['entry_price']:.2f} -> Salida: ${fill_price:.2f}\n"
                      f"PnL: ${pnl:+.2f}")

    record_trade({
        "entry_time": pos["entry_time"],
        "exit_time": datetime.now(timezone.utc).isoformat(),
        "entry_price": pos["entry_price"],
        "exit_price": fill_price,
        "quantity": pos["quantity"],
        "pnl_usd": round(pnl, 4),
        "exit_reason": reason,
    })
    state["position"] = None
    save_state(state)


def cycle(client, state):
    df = get_recent_klines(client)
    price = float(client.get_symbol_ticker(symbol=config.SYMBOL)["price"])
    df_sig = generate_signals(df.copy())
    candle_id = str(df_sig["open_time"].iloc[-2])  # ultima vela CERRADA
    last = df_sig.iloc[-2]
    atr = float(df["atr"].iloc[-1]) if "atr" in df else price * 0.01
    atr = float(df_sig["atr"].iloc[-1])

    pos = state["position"]

    # Gestion de posicion abierta: trailing stop 4xATR
    if pos:
        pos["highest_close"] = max(pos["highest_close"], price)
        trail_stop = pos["highest_close"] - ATR_STOP_MULT * atr
        pos["stop_loss"] = max(pos["stop_loss"], trail_stop)
        save_state(state)
        if price <= pos["stop_loss"]:
            reason = "TRAILING_STOP" if pos["stop_loss"] > pos["entry_price"] else "STOP_LOSS"
            close_position(client, state, price, reason)
            return

    # Senales de la ultima vela cerrada (una sola vez por vela)
    if candle_id in state["processed_candles"]:
        return

    if pos is None and last["signal"] == 1:
        open_position(client, state, float(last["close"]),
                      float(last["atr"]), candle_id)

    state["processed_candles"].append(candle_id)
    state["processed_candles"] = state["processed_candles"][-50:]
    save_state(state)


def show_status(state):
    pos = state.get("position")
    if pos:
        print(f"POSICION ABIERTA: {pos['quantity']} {config.SYMBOL} "
              f"@ {pos['entry_price']:.2f}")
        print(f"  Trailing stop: {pos['stop_loss']:.2f} | "
              f"Maximo: {pos['highest_close']:.2f}")
    else:
        print("Sin posicion abierta. Esperando pullback en tendencia "
              "(RSI<30 sobre EMA200).")
    import os
    if os.path.exists(LOG_FILE):
        df = pd.read_csv(LOG_FILE)
        wins = (df["pnl_usd"] > 0).sum()
        print(f"\nHistorial: {len(df)} trades | Wins: {wins} | "
              f"Win rate: {wins/len(df)*100:.1f}% | "
              f"PnL total: ${df['pnl_usd'].sum():+.2f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    state = load_state()
    if args.status:
        show_status(state)
        return

    client = get_client()
    print(f"Paper trading E2 | {config.SYMBOL} {config.INTERVAL} | "
          f"EMA200 pend+ | RSI(6)<30 | Trail 4xATR | Expos 25%")

    if args.once:
        cycle(client, state)
        print("Ciclo unico completado.")
        return

    try:
        while True:
            try:
                cycle(client, state)
            except Exception as e:
                log(f"ERROR en ciclo: {e}")
            time.sleep(CHECK_INTERVAL)
    except KeyboardInterrupt:
        print("\nBot detenido por el usuario.")


if __name__ == "__main__":
    main()
