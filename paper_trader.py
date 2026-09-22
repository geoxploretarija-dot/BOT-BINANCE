"""Paper trading en Binance Testnet - Estrategia 2 (Tendencia + Pullback).

Parametros optimizados (validados en mercado alcista Y bajista):
  - Entrada: precio > EMA200 (pendiente positiva) y RSI(6) < 30
  - Salida: trailing stop de 4x ATR (las ganancias corren)
  - Exposicion maxima: 25% del capital por trade
  - Riesgo: 2% del capital por trade (efectivo ~0.5%: el sizing limita
    por exposicion maxima; ver README)

Protecciones en vivo (solo bloquean entradas, nunca las generan):
  - Maximo 3 trades por dia (UTC)
  - Cooldown de 4h tras un stop-loss perdedor
  - No entra con volatilidad extrema (ATR > 1.5% del precio)
  - Alerta por Telegram si hay huecos de velas (caida/reinicio)

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
from datetime import datetime, timezone, timedelta

import pandas as pd

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import config
import storage
from client import get_client
from strategy2 import generate_signals, ATR_STOP_MULT
import telegram_bot

STATE_FILE = "paper_state2.json"
TRADES_FILE = "paper_trades2.json"
LOG_FILE = "paper_trades2.csv"  # compatibilidad (CSV local)
CHECK_INTERVAL = 60  # segundos entre chequeos de precio
MAX_EXPOSURE = 0.25  # 25% del capital maximo por trade

# Protecciones en vivo
MAX_TRADES_PER_DAY = 3  # maximo de entradas por dia (UTC)
COOLDOWN_HOURS = 4      # pausa tras un stop-loss perdedor
MAX_ATR_PCT = 0.015     # no entra si ATR > 1.5% del precio


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_state() -> dict:
    state = storage.load_json(STATE_FILE,
                              {"position": None, "processed_candles": []})
    return state


def save_state(state: dict, sync: bool = False):
    storage.save_json(STATE_FILE, state, sync=sync)


def alert_gap_if_any(state: dict, candle_id: str):
    """Si la ultima vela cerrada no es consecutiva con la ultima procesada,
    hubo velas sin ciclar (caida/reinicio de Render). Avisa una sola vez."""
    processed = state["processed_candles"]
    if not processed or state.get("gap_alerted") == candle_id:
        return
    try:
        prev = pd.Timestamp(processed[-1])
        curr = pd.Timestamp(candle_id)
        gap_h = (curr - prev).total_seconds() / 3600
        if gap_h > 1.5:
            state["gap_alerted"] = candle_id
            save_state(state)
            log(f"HUECO DE VELAS: {gap_h:.0f}h sin ciclar ({prev} -> {curr})")
            telegram_bot.send(f"⚠️ Hueco de velas: {gap_h:.0f}h sin ciclar\n"
                              f"({prev} -> {curr}). Posible caida/reinicio.")
    except Exception as e:
        log(f"WARN gap check: {e}")


def trades_today_count(state: dict) -> int:
    """Numero de entradas de hoy (UTC). Reinicia el contador cada dia."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    t = state.get("trades_today") or {}
    if t.get("date") != today:
        t = {"date": today, "count": 0}
        state["trades_today"] = t
    return int(t["count"])


def cooldown_active(state: dict) -> bool:
    """True si aun corre la pausa tras un stop-loss perdedor."""
    ts = state.get("last_stop_time")
    if not ts:
        return False
    try:
        elapsed = datetime.now(timezone.utc) - datetime.fromisoformat(ts)
        return elapsed < timedelta(hours=COOLDOWN_HOURS)
    except (ValueError, TypeError):
        return False


def recover_position_from_market(client, state: dict):
    """Si hay posicion abierta y el proceso reincicio, recalcula el
    trailing stop recorriendo las velas desde la entrada (hace que el
    sistema tolere redespliegues sin perder el estado de riesgo)."""
    pos = state.get("position")
    if not pos:
        return
    df = get_recent_klines(client, limit=500)
    entry_ts = pd.Timestamp(pos["entry_time"])
    after = df[df["open_time"] >= entry_ts]
    if after.empty:
        return
    after = after.iloc[:-1]  # solo velas CERRADAS (igual que el ciclo en vivo)
    if after.empty:
        return
    d = generate_signals(df.copy())
    atr_series = d["atr"]
    stop = pos["stop_loss"]
    highest = pos["highest_close"]
    for ts, row in after.iterrows():
        atr = float(atr_series.get(ts, atr_series.iloc[-1]))
        highest = max(highest, float(row["close"]))
        stop = max(stop, highest - ATR_STOP_MULT * atr)
    if stop != pos["stop_loss"] or highest != pos["highest_close"]:
        pos["stop_loss"] = stop
        pos["highest_close"] = highest
        save_state(state, sync=True)
    log(f"Recuperada posicion: stop trailing recalculado ${pos['stop_loss']:.2f}")


def record_trade(row: dict):
    """Guarda el trade en CSV local y en el JSON sincronizado a GitHub."""
    import os
    df = pd.DataFrame([row])
    df.to_csv(LOG_FILE, mode="a", index=False, header=not os.path.exists(LOG_FILE))
    trades = storage.load_json(TRADES_FILE, [])
    trades.append(row)
    storage.save_json(TRADES_FILE, trades, sync=True)


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
    save_state(state, sync=True)


def close_position(client, state, price: float, reason: str):
    pos = state["position"]
    if pos is None:
        return
    # Vende el balance real disponible (los fees pueden reducir el BTC
    # recibido en la compra), sin exceder la cantidad de la posicion.
    base = config.SYMBOL.replace("USDT", "")
    available = float(client.get_asset_balance(base)["free"])
    quantity = round_step(client, config.SYMBOL, min(available, pos["quantity"]))
    if quantity > 0:
        order = client.order_market_sell(symbol=config.SYMBOL, quantity=quantity)
        fill_price = float(order["fills"][0]["price"]) if order.get("fills") else price
    else:
        log("Cantidad a vender demasiado pequena (dust). Cierre sin orden.")
        fill_price = price
    pnl = (fill_price - pos["entry_price"]) * pos["quantity"]
    log(f"VENTA {quantity} {config.SYMBOL} @ {fill_price:.2f} | "
        f"PnL: ${pnl:+.2f} ({reason})")
    emoji = "🟢" if pnl > 0 else "🔴"
    telegram_bot.send(f"{emoji} VENTA {config.SYMBOL} ({reason})\n"
                      f"Entrada: ${pos['entry_price']:.2f} -> Salida: ${fill_price:.2f}\n"
                      f"PnL: ${pnl:+.2f}")

    if reason == "STOP_LOSS":
        state["last_stop_time"] = datetime.now(timezone.utc).isoformat()

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
    save_state(state, sync=True)


def cycle(client, state):
    df = get_recent_klines(client)
    price = float(client.get_symbol_ticker(symbol=config.SYMBOL)["price"])
    df_sig = generate_signals(df.copy())
    candle_id = str(df_sig["open_time"].iloc[-2])  # ultima vela CERRADA
    last = df_sig.iloc[-2]
    atr = float(df_sig["atr"].iloc[-2])  # ATR de la ultima vela cerrada

    # Alerta de huecos de velas (caida/reinicio), solo al llegar vela nueva
    if candle_id not in state["processed_candles"]:
        alert_gap_if_any(state, candle_id)

    pos = state["position"]

    # Gestion de posicion abierta: trailing stop 4xATR.
    # El maximo se rige por CIERRES de vela (igual que la recuperacion tras
    # reinicio y el backtest); la salida se dispara con el precio en vivo.
    if pos:
        pos["highest_close"] = max(pos["highest_close"], float(last["close"]))
        trail_stop = pos["highest_close"] - ATR_STOP_MULT * atr
        pos["stop_loss"] = max(pos["stop_loss"], trail_stop)
        save_state(state)
        if price <= pos["stop_loss"]:
            reason = "TRAILING_STOP" if pos["stop_loss"] > pos["entry_price"] else "STOP_LOSS"
            close_position(client, state, price, reason)
            state["processed_candles"].append(candle_id)
            state["processed_candles"] = state["processed_candles"][-50:]
            save_state(state, sync=True)
            return

    # Senales de la ultima vela cerrada (una sola vez por vela)
    if candle_id in state["processed_candles"]:
        return

    if pos is None and last["signal"] == 1:
        entry_price = float(last["close"])
        entry_atr = float(last["atr"])
        if trades_today_count(state) >= MAX_TRADES_PER_DAY:
            log("Maximo de trades por dia alcanzado. No se abre posicion.")
        elif cooldown_active(state):
            log("Cooldown post stop-loss activo. No se abre posicion.")
        elif entry_atr / entry_price > MAX_ATR_PCT:
            log(f"Volatilidad extrema (ATR {entry_atr / entry_price * 100:.2f}%). "
                "No se abre posicion.")
        else:
            open_position(client, state, entry_price, entry_atr, candle_id)
            if state["position"]:
                state["trades_today"]["count"] = trades_today_count(state) + 1

    state["processed_candles"].append(candle_id)
    state["processed_candles"] = state["processed_candles"][-50:]
    save_state(state, sync=True)


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
