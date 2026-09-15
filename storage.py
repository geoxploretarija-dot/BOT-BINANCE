"""Capa de persistencia: archivo local + espejo en GitHub (Contents API).

- Escritura local siempre (rapidez)
- Sincronizacion a GitHub solo cuando sync=True (eventos clave)
- Lectura: prioriza GitHub (sobrevive a redespliegues en Render),
  con fallback al archivo local.

Variables de entorno requeridas para el espejo:
  GITHUB_TOKEN  (PAT con permiso de contenido del repo)
  GITHUB_REPO   (ej: "geoxploretarija-dot/BOT-BINANCE")
"""
import os
import json
import base64
import requests

import config  # carga .env

TOKEN = os.getenv("GITHUB_TOKEN", "")
REPO = os.getenv("GITHUB_REPO", "geoxploretarija-dot/BOT-BINANCE")
BRANCH = "main"
BASE = f"https://api.github.com/repos/{REPO}/contents/"
_sha_cache = {}


def _headers():
    return {"Authorization": f"Bearer {TOKEN}",
            "Accept": "application/vnd.github+json"}


def _remote_get(path):
    r = requests.get(BASE + path, headers=_headers(),
                     params={"ref": BRANCH}, timeout=15)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    data = r.json()
    _sha_cache[path] = data["sha"]
    return json.loads(base64.b64decode(data["content"]).decode())


def _remote_put(path, payload: dict):
    body = {"message": f"estado: {path}", "branch": BRANCH,
            "content": base64.b64encode(
                json.dumps(payload, indent=2).encode()).decode()}
    if path in _sha_cache:
        body["sha"] = _sha_cache[path]
    else:
        r0 = requests.get(BASE + path, headers=_headers(),
                          params={"ref": BRANCH}, timeout=15)
        if r0.status_code == 200:
            body["sha"] = r0.json()["sha"]
    r = requests.put(BASE + path, headers=_headers(), json=body, timeout=15)
    if r.status_code in (200, 201):
        _sha_cache[path] = r.json()["content"]["sha"]
    else:
        raise RuntimeError(f"GitHub PUT {path}: {r.status_code} {r.text[:200]}")


def load_json(path: str, default):
    """Carga JSON: GitHub si hay token, si no, archivo local."""
    if TOKEN:
        try:
            remote = _remote_get(path)
            if remote is not None:
                with open(path, "w") as f:
                    json.dump(remote, f, indent=2)
                return remote
        except Exception as e:
            print(f"WARN storage remoto (load {path}): {e}", flush=True)
    try:
        with open(path) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path: str, data, sync: bool = False):
    """Guarda local; si sync=True y hay token, espejo a GitHub."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)
    if sync and TOKEN:
        try:
            _remote_put(path, data)
        except Exception as e:
            print(f"WARN storage remoto (save {path}): {e}", flush=True)
