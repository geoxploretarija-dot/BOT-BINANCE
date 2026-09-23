"""Cliente de Binance configurado segun entorno (testnet/real)."""
import sys
from binance.client import Client
import config

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_client() -> Client:
    if not config.API_KEY or not config.SECRET_KEY:
        raise ValueError("Faltan credenciales. Completa el archivo .env")
    # Timeout explicito: una llamada colgada falla a los 15s en vez de
    # dejar el ciclo trabado indefinidamente (reintenta en 60s)
    client = Client(config.API_KEY, config.SECRET_KEY,
                    testnet=config.USE_TESTNET,
                    requests_params={"timeout": 15})
    return client


def check_connection():
    client = get_client()
    client.ping()
    account = client.get_account()
    balances = [b for b in account["balances"]
                if float(b["free"]) > 0 or float(b["locked"]) > 0]
    print(f"Conexion OK ({'TESTNET' if config.USE_TESTNET else 'REAL'})")
    print("Balances:")
    for b in balances:
        print(f"  {b['asset']}: free={b['free']} locked={b['locked']}")
    return client


if __name__ == "__main__":
    check_connection()
