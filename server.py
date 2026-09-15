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

app = Flask(__name__)
bot_state = {"last_cycle": None, "errors": 0, "running": False}


def bot_loop():
    bot_state["running"] = True
    client = get_client()
    state = paper_trader.load_state()
    while True:
        try:
            paper_trader.cycle(client, state)
            bot_state["last_cycle"] = time.strftime("%Y-%m-%d %H:%M:%S",
                                                    time.gmtime())
            bot_state["errors"] = 0
        except Exception as e:
            bot_state["errors"] += 1
            print(f"ERROR ciclo: {e}", flush=True)
        time.sleep(paper_trader.CHECK_INTERVAL)


@app.get("/")
def home():
    return "Bot activo", 200


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
        "open_position": pos,
    })


if __name__ == "__main__":
    t = threading.Thread(target=bot_loop, daemon=True)
    t.start()
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
