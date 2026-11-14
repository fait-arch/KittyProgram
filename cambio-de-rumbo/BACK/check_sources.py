"""Prueba todas las fuentes de docs/APIS-DATOS.md y muestra ✅ / ⚠️ / ❌.

    python check_sources.py
"""
import traceback

from app.core import gee
from app.core.config import settings
from app.core.supabase import check_supabase
from app.sources import ecocrop, espac, faostat, gbif, gee_data, noaa, power, sipa

LAT, LON = -1.80, -79.53  # Babahoyo, Los Ríos
results = []


def check(n, name, fn):
    try:
        detail = fn()
        results.append(("✅", n, name, detail))
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).splitlines()[0][:110] if str(exc) else exc.__class__.__name__
        results.append(("❌", n, name, msg))


def skip(n, name, reason):
    results.append(("⚠️ ", n, name, reason))


# Sin cuenta
check(1, "NOAA ONI", lambda: f"último {noaa.fetch_oni(False)[-1]}")
check(2, "NOAA Niño 1+2", lambda: f"último {[r for r in noaa.fetch_nino(False) if r['index_id']=='nino12_anom'][-1]}")
check(9, "ECOCROP", lambda: (lambda r: f"{r['cientifico']}: {r['temp_opt_min_c']}–{r['temp_opt_max_c']} °C, "
                                       f"{r['lluvia_opt_min_mm']}–{r['lluvia_opt_max_mm']} mm")(ecocrop.get_requirements()))
check(13, "NASA POWER", lambda: f"{len(power.power_climatology(LAT, LON, False)['meses'])} meses de climatología")
check(14, "GBIF", lambda: f"{len(gbif.fetch_occurrences('monilia', use_cache=False))} registros con coordenadas")

# Descargas / archivos manuales
if faostat.zip_path().exists():
    check(11, "FAOSTAT", lambda: f"{len(faostat.load_country_series())} filas Ecuador")
else:
    skip(11, "FAOSTAT", "ZIP no descargado aún: python -c \"from app.sources import faostat; faostat.ensure_zip()\"")
files = espac.list_files()
skip(10, "ESPAC (INEC)", f"archivos: {files}" if files else "manual: guardar XLSX en data/raw/espac/")
check(12, "SIPA (MAG)", lambda: f"{len(sipa.load_prices())} precios") if \
    (settings.data_raw_path / "sipa" / "precios_cacao.csv").exists() else \
    skip(12, "SIPA (MAG)", "manual: guardar data/raw/sipa/precios_cacao.csv")

# Google Earth Engine
if gee.init_gee():
    geom = gee_data.point_area(LAT, LON)
    check(8, "GEE · FAO GAUL", lambda: f"{len(gee_data.canton_list(['Los Rios']))} cantones en Los Ríos")
    check(6, "GEE · MODIS/GPM/SMAP", lambda: f"ene-2023: {gee_data.monthly_series(geom, 2023)[0]}")
    check(7, "GEE · SRTM/suelo/WorldCover", lambda: gee_data.static_features(geom))
else:
    for n, name in [(3, "ERA5-Land"), (4, "GPM IMERG"), (5, "SMAP"), (6, "MODIS"),
                    (7, "SRTM/suelo/WorldCover"), (8, "FAO GAUL"), (15, "CMIP6")]:
        skip(n, f"GEE · {name}", f"GEE no listo: {(gee.GEE_ERROR or '')[:70]}")

# Cuentas
ok, err = check_supabase()
results.append(("✅" if ok else "❌", "—", "Supabase", "conectado" if ok else err))
skip(16, "ECOSTRESS (AppEEARS)", "credenciales OK (Fase 3)" if settings.earthdata_configured
     else "Fase 3: falta EARTHDATA_USER/PASS")

print(f"\n{'':3} {'#':>2}  {'Fuente':30} Detalle")
print("─" * 100)
for icon, n, name, detail in sorted(results, key=lambda r: (999 if r[1] == "—" else r[1])):
    print(f"{icon:3} {str(n):>2}  {name:30} {str(detail)[:110]}")
