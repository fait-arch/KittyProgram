"""Punto de entrada (comando de docs/02-configuracion.md):

    python -m uvicorn run:app --reload --host 0.0.0.0 --port 8000
"""
from app.main import app  # noqa: F401
