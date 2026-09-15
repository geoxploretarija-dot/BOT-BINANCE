"""Integracion Telegram: comandos interactivos + alertas automaticas.

Comandos:
  /start    -> registra tu chat y recibes alertas automaticas de trades
  /status   -> estado del bot, posicion abierta, errores
  /resumen  -> historial de trades, win rate, PnL
  /mercado  -> analisis tecnico actual (EMA200, RSI)

Alertas automaticas: el bot te escribe cuando abre/cierra operaciones.
"""
import os
import json
import time
import threading
import requests
import pandas as pd

import config  # carga .env (dotenv) antes de leer el token

TOKEN = os.getenv("TELEGRAM_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
CHAT_FILE = "telegram_chat.json"
POLL_TIMEOUT = 30  # segundos (long polling)

# Estado del bot de trading, inyectado desde server.py
shared = {"bot_state": None}


def _chat_id() -> str:
    try:
        with open(CHAT_FILE) as f:
            return json.load(f).get("chat_id", "")
    except Exception:
        return ""


def _save_chat_id(cid: str):
    with open(CHAT_FILE, "w") as f:
        json.dump({"chat_id": cid}, f)


def send(text: str, chat_id: str = None):
    """Envia mensaje. Si no hay chat_id, usa el registrado con /start."""
    cid = chat_id or _chat_id()
    if not TOKEN or not cid:
        return
    try:
        requests.post(f"{API}/sendMessage",
                      data={"chat_id": cid, "text": text}, timeout=10)
    except Exception as e:
        print(f"ERROR telegram send: {e}", flush=True)


def _fmt_status() -> str:
    bs = shared.get("bot_state") or {}
    try:
        import paper_trader
        pos = paper_trader.load_state().get("position")
    except Exception:
        pos = None
    lines = [f"🤖 BOT: {'🟢 ACTIVO' if bs.get('running') else '🔴 DETENIDO'}",
             f"Ultimo ciclo: {bs.get('last_cycle', 'arrancando...')}",
             f"Errores: {bs.get('errors', 0)}"]
    if bs.get("fatal"):
        lines.append(f"⚠️ FATAL: {bs['fatal']}")
    if pos:
        lines.append(f"\n📈 POSICION ABIERTA:")
        lines.append(f"  Entrada: ${pos['entry_price']:.2f}")
        lines.append(f"  Cantidad: {pos['quantity']}")
        lines.append(f"  Trailing stop: ${pos['stop_loss']:.2f}")
    else:
        lines.append("\nSin posicion abierta. Esperando senal.")
    return "\n".join(lines)


def _fmt_resumen() -> str:
    try:
        df = pd.read_csv("paper_trades2.csv")
    except Exception:
        return "Aun no hay trades registrados."
    wins = (df["pnl_usd"] > 0).sum()
    n = len(df)
    return (f"📊 RESUMEN\n"
            f"Trades: {n} | Wins: {wins} ({wins/n*100:.0f}%)\n"
            f"PnL total: ${df['pnl_usd'].sum():+.2f}\n"
            f"Mejor: ${df['pnl_usd'].max():+.2f} | Peor: ${df['pnl_usd'].min():+.2f}")


def _fmt_mercado() -> str:
    try:
        from data import get_historical_klines
        from strategy2 import add_indicators
        import config
        df = get_historical_klines(config.SYMBOL, config.INTERVAL, "3 months ago UTC")
        d = add_indicators(df)
        last = d.iloc[-1]
        slope_pct = (last["ema200"] / d["ema200"].iloc[-11] - 1) * 100
        dist = (last["close"] / last["ema200"] - 1) * 100
        c1 = last["close"] > last["ema200"]
        c2 = slope_pct > 0
        c3 = last["rsi"] < 30
        return (f"📈 MERCADO {config.SYMBOL}\n"
                f"Precio: ${last['close']:,.0f}\n"
                f"EMA200: ${last['ema200']:,.0f} ({dist:+.1f}%)\n"
                f"Pendiente EMA: {slope_pct:+.2f}%\n"
                f"RSI(6): {last['rsi']:.1f}\n\n"
                f"{'✅' if c1 else '❌'} Precio sobre EMA200\n"
                f"{'✅' if c2 else '❌'} Pendiente positiva\n"
                f"{'✅' if c3 else '❌'} RSI < 30 (pullback)\n"
                f"{'🟢 SENAL ACTIVA' if (c1 and c2 and c3) else '⏸ Esperando'}")
    except Exception as e:
        return f"Error obteniendo mercado: {e}"


def handle(text: str, chat_id: str) -> str:
    cmd = text.strip().split("@")[0].lower()
    if cmd in ("/start", "/help"):
        _save_chat_id(chat_id)
        send("✅ Chat registrado. Recibiras alertas de trades automaticamente.", chat_id)
        return ("Comandos:\n/status - estado del bot\n"
                "/resumen - historial de trades\n/mercado - analisis actual")
    if cmd == "/status":
        return _fmt_status()
    if cmd == "/resumen":
        return _fmt_resumen()
    if cmd == "/mercado":
        return _fmt_mercado()
    return "Comando no reconocido. Prueba /help"


def poll_loop():
    """Long polling: escucha comandos de Telegram en segundo plano."""
    if not TOKEN:
        print("TELEGRAM_TOKEN no configurado, poller desactivado", flush=True)
        return
    offset = 0
    while True:
        try:
            r = requests.get(f"{API}/getUpdates",
                             params={"offset": offset, "timeout": POLL_TIMEOUT},
                             timeout=POLL_TIMEOUT + 10)
            for upd in r.json().get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                text, cid = msg.get("text", ""), str(msg.get("chat", {}).get("id", ""))
                if text.startswith("/") and cid:
                    try:
                        send(handle(text, cid), cid)
                    except Exception as e:
                        send(f"Error procesando comando: {e}", cid)
        except Exception as e:
            print(f"ERROR telegram poll: {e}", flush=True)
            time.sleep(5)


def start_background(bot_state: dict):
    """Arranca el poller y enlaza el estado del bot para /status."""
    shared["bot_state"] = bot_state
    threading.Thread(target=poll_loop, daemon=True).start()
