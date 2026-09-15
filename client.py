"""Cliente de Binance configurado segun entorno (testnet/real)."""
import sys
from binance.client import Client
import config

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def get_client() -> Client:
    if not config.API_KEY or not config.SECRET_KEY:
        raise ValueError("Faltan credenciales. Completa el archivo .env")
    client = Client(config.API_KEY, config.SECRET_KEY, testnet=config.USE_TESTNET)
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
