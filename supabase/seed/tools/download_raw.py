"""Descarga las fuentes crudas del seed. Uso: python download_raw.py <carpeta_raw>

Luego: fetch_weather.py <raw>, fetch_static.py <raw> y build_seed.py <raw> ../data
"""
import sys
import urllib.request
from pathlib import Path

RAW = Path(sys.argv[1])
RAW.mkdir(parents=True, exist_ok=True)
GB = "https://github.com/wmgeolab/geoBoundaries/raw/9469f09/releaseData/gbOpen/ECU"
FILES = {
    "adm1.geojson": f"{GB}/ADM1/geoBoundaries-ECU-ADM1_simplified.geojson",
    "adm2.geojson": f"{GB}/ADM2/geoBoundaries-ECU-ADM2_simplified.geojson",
    "oni.txt": "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt",
    "sstoi.txt": "https://www.cpc.ncep.noaa.gov/data/indices/sstoi.indices",
    "fred_cocoa.csv": "https://fred.stlouisfed.org/graph/fredgraph.csv?id=PCOCOUSDM",
    "faostat_americas.zip": "https://bulks-faostat.fao.org/production/Production_Crops_Livestock_E_Americas.zip",
    "gbif_monilia.json": "https://api.gbif.org/v1/occurrence/search?scientificName=Moniliophthora%20roreri&country=EC&hasCoordinate=true&limit=300",
    "admgz.xlsx": "https://data.humdata.org/dataset/ab3c7592-3b0c-41cd-999a-2919a6b243f2/resource/e59b7aaf-755d-47e5-95e4-a98f9bfa5856/download/ecu_admgz.xlsx",
    "espac_tab2025.xlsx": "https://www.ecuadorencifras.gob.ec/documentos/web-inec/Estadisticas_agropecuarias/espac/2025/Tabulados_excel_2025.xlsx",
    "espac_tab2024.xlsx": "https://www.ecuadorencifras.gob.ec/documentos/web-inec/Estadisticas_agropecuarias/espac/2024/Tabulados_ESPAC_2024.xlsx",
    "espac_tab2023.xlsx": "https://www.ecuadorencifras.gob.ec/documentos/web-inec/Estadisticas_agropecuarias/espac/2023/Tabulados_ESPAC_2023.xlsx",
    "gbif_perniciosa.json": "https://api.gbif.org/v1/occurrence/search?scientificName=Moniliophthora%20perniciosa&country=EC&hasCoordinate=true&limit=300",
}
for name, url in FILES.items():
    print("↓", name, flush=True)
    urllib.request.urlretrieve(url, RAW / name)
print("Listo. Siguiente: fetch_weather.py")
