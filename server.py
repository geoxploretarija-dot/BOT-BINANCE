"""Servidor envoltorio para desplegar el bot en Render/similares.

- Ejecuta el paper_trader en un hilo de fondo (loop infinito)
- Expone un endpoint web:
    GET /        -> vivo (para health checks / Render)
    GET /status  -> estado del bot y ultimas operaciones
- Render exige escuchar en el puerto de la variable de entorno PORT
"""
import os
import threading
import time
from flask import Flask, jsonify

from client import get_client
import paper_trader
import telegram_bot

app = Flask(__name__)
bot_state = {"last_cycle": None, "errors": 0, "running": False}


def bot_loop():
    try:
        client = get_client()
        state = paper_trader.load_state()
        bot_state["running"] = True
    except Exception as e:
        bot_state["errors"] += 1
        bot_state["fatal"] = str(e)
        return
    while True:
        try:
            paper_trader.cycle(client, state)
            bot_state["last_cycle"] = time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.gmtime())
            bot_state["errors"] = 0
        except Exception as e:
            bot_state["errors"] += 1
            bot_state["last_error"] = f"{type(e).__name__}: {e}"
            print(f"ERROR ciclo: {e}", flush=True)
        time.sleep(paper_trader.CHECK_INTERVAL)


@app.get("/")
def home():
    return "Bot activo", 200


@app.get("/report")
def report():
    """Resumen detallado para monitoreo programado (GitHub Actions)."""
    import json
    import os
    import pandas as pd
    out = {"bot": bot_state, "position": None, "trades": None}
    try:
        with open(paper_trader.STATE_FILE) as f:
            out["position"] = json.load(f).get("position")
    except Exception:
        pass
    if os.path.exists(paper_trader.LOG_FILE):
        df = pd.read_csv(paper_trader.LOG_FILE)
        wins = int((df["pnl_usd"] > 0).sum())
        out["trades"] = {
            "total": len(df), "wins": wins,
            "win_rate": round(wins / len(df) * 100, 1),
            "pnl_total": round(float(df["pnl_usd"].sum()), 2),
            "least_5": df.tail(5).to_dict("records"),
        }
    return jsonify(out)


@app.get("/status")
def status():
    import json
    try:
        with open(paper_trader.STATE_FILE) as f:
            pos = json.load(f).get("position")
    except Exception:
        pos = None
    return jsonify({
        "running": bot_state["running"],
        "last_cycle": bot_state["last_cycle"],
        "errors": bot_state["errors"],
        "fatal": bot_state.get("fatal"),
        "last_error": bot_state.get("last_error"),
        "open_position": pos,
        "telegram_chat_id": telegram_bot._chat_id(),
    })


if __name__ == "__main__":
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    telegram_bot.start_background(bot_state)
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
