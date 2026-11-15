"""Inicialización de Google Earth Engine.

Orden de autenticación:
1. GEE_PRIVATE_KEY_JSON  (JSON de la cuenta de servicio pegado en la variable)
2. GEE_PRIVATE_KEY_PATH  (ruta al JSON de la cuenta de servicio)
3. Sesión local de `earthengine authenticate`
"""
import json
import os
from pathlib import Path

import ee
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

_ready = False


def init_gee() -> None:
    global _ready
    if _ready:
        return
    project = os.getenv("GEE_PROJECT")
    if not project:
        raise RuntimeError("Falta GEE_PROJECT en BACK/.env (ver BACK/.env.example)")

    key_json = os.getenv("GEE_PRIVATE_KEY_JSON")
    key_path = os.getenv("GEE_PRIVATE_KEY_PATH")
    if key_json:
        email = json.loads(key_json)["client_email"]
        ee.Initialize(ee.ServiceAccountCredentials(email, key_data=key_json), project=project)
    elif key_path:
        email = json.loads(Path(key_path).read_text())["client_email"]
        ee.Initialize(ee.ServiceAccountCredentials(email, key_path), project=project)
    else:
        ee.Initialize(project=project)
    _ready = True
