"""Configuración compartida del modelo CacaoResiliente."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_RAW = ROOT / "data" / "raw"
DATA_PROCESSED = ROOT / "data" / "processed"
ARTIFACTS = ROOT / "artifacts"

# Provincias cacaoteras (nombres FAO GAUL nivel 1)
PROVINCES = ["Los Rios", "Guayas", "Manabi", "Esmeraldas", "El Oro", "Santo Domingo de los Tsachilas", "Sucumbios"]

# Rango de años: lo más largo posible (FAOSTAT desde 1961, ERA5-Land desde 1950)
YEAR_START, YEAR_END = 1961, 2025

# Época lluviosa de la Costa (meses usados para agregar features)
RAINY_MONTHS = list(range(1, 7))

# ECOCROP Theobroma cacao (TMIN, TOPMN, TOPMX, TMAX) y (RMIN, ROPMN, ROPMX, RMAX)
ECOCROP_T = (10, 21, 32, 38)
ECOCROP_R = (900, 1200, 3000, 7600)
