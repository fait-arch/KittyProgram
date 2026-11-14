"""Acceso a datos NASA (Google Earth Engine + NASA POWER) para el equipo.

Uso rápido:
    from nasa_data import init_gee, monthly_series, power_monthly
    init_gee()
    df = monthly_series(lon=-79.53, lat=-1.80, start="2020-01-01", end="2025-01-01")
"""
from .gee import init_gee
from .series import VARIABLES, monthly_series
from .power import power_monthly

__all__ = ["init_gee", "monthly_series", "power_monthly", "VARIABLES"]
