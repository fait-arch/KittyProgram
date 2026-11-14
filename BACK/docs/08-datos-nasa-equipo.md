# 7. Datos NASA para el equipo (`BACK/nasa_data`)

Módulo para que cualquiera del equipo saque series mensuales NASA (para el modelo de
predicción, notebooks o el backend) sin tocar la consola de Google.

## Configuración (una vez)

```bash
cd BACK
python -m venv venv
venv/bin/pip install -r nasa_data/requirements.txt      # Windows: venv\Scripts\pip
cp .env.example .env                                    # y pon GEE_PROJECT=proyectito-uwu-514715
```

Autenticación, elige una:

- **Con tu cuenta de Google** (tienes que estar agregado al proyecto de Google Cloud
  `proyectito-uwu-514715` con rol *Earth Engine Resource Viewer* + *Service Usage Consumer*):
  `venv/bin/earthengine authenticate`
- **Con la llave de la cuenta de servicio** (pídela por privado, NUNCA al repo):
  guárdala como `BACK/gee-key.json` y añade en `.env`:
  `GEE_PRIVATE_KEY_PATH=gee-key.json`

## Uso desde la terminal (CSV)

```bash
# Punto (Babahoyo), 2020–2024
venv/bin/python -m nasa_data --lon -79.53 --lat -1.80 --start 2020-01-01 --end 2025-01-01 -o babahoyo.csv

# Polígono (cantón o finca en GeoJSON)
venv/bin/python -m nasa_data --geojson canton.geojson -o canton.csv
```

## Uso desde Python / notebook

```python
from nasa_data import monthly_series, power_monthly

df  = monthly_series(lon=-79.53, lat=-1.80, start="2015-04-01", end="2025-01-01")
clima = power_monthly(-79.53, -1.80, 2015, 2024)
data = df.merge(clima, on="month_date")
```

## Columnas

| Columna | Fuente | Unidad |
|---------|--------|--------|
| `precip` | GPM IMERG (GEE) | mm/mes |
| `soil_moisture_surf`, `soil_moisture_root` | SMAP L4 (GEE), desde 2015-04 | m³/m³ |
| `ndvi` | MODIS MOD13Q1 (GEE) | índice 0–1 |
| `lst_day` | MODIS MOD11A2 (GEE) | °C |
| `et_actual` | MODIS MOD16A2GF (GEE) | mm/mes |
| `t2m`, `t2m_max`, `t2m_min` | NASA POWER | °C |
| `rh2m` | NASA POWER | % |
| `solar_rad` | NASA POWER | MJ/m²/día |
| `ws2m` | NASA POWER | m/s |
| `precip_power` | NASA POWER | mm/día |

Los nombres coinciden con la tabla `variables` de Supabase, así se puede subir a
`area_monthly_series` directamente.

## Notas

- `lst_day` y `ndvi` salen vacíos (NaN) en meses muy nublados si consultas **un punto**.
  Con un polígono (cantón) hay muchos más píxeles y casi no pasa.
- Un punto dentro de una ciudad da NDVI bajo: usa coordenadas de cultivo o un polígono.
- Límites de GEE: no lances muchos scripts en paralelo; guarda los CSV y reutilízalos.
