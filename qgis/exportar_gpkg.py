"""Exporta capas de CacaoResiliente a un GeoPackage que QGIS abre con la leyenda lista.

QGIS guarda los estilos de un GeoPackage en la tabla `layer_styles`; al abrir una capa
aplica el estilo marcado `useAsDefault`. Este módulo escribe las capas y esa tabla con los
estilos de `estilos/` (.qml para QGIS y .sld para otros SIG).

Uso desde el backend (endpoint de exportación):

    from exportar_gpkg import write_styled_gpkg
    write_styled_gpkg({"perdida_nino": gdf_nino, "zonas_2050": gdf_zonas}, "salida.gpkg")

Uso por línea de comandos:

    python exportar_gpkg.py salida.gpkg perdida_nino=nino.geojson zonas_2050=zonas.geojson

El estilo se elige por el nombre de la capa: las que empiezan con `zonas` usan
`zonas_2050`; el resto usa `perdida_cacao` (campo `loss_pct`).

Requiere: geopandas >= 1.0 y pyogrio (incluye GDAL con soporte GeoPackage).
"""
from __future__ import annotations

import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio

ESTILOS = Path(__file__).resolve().parent / "estilos"
GEOM_COL = "geom"  # nombre de columna de geometría por defecto de GDAL en GeoPackage


def style_for(layer: str) -> str:
    return "zonas_2050" if layer.startswith("zonas") else "perdida_cacao"


def write_styled_gpkg(
    layers: dict[str, gpd.GeoDataFrame],
    path: str | Path,
    styles: dict[str, str] | None = None,
    descriptions: dict[str, str] | None = None,
) -> Path:
    """Escribe cada GeoDataFrame como capa y registra su estilo QML/SLD por defecto."""
    path = Path(path)
    if path.exists():
        path.unlink()
    styles = styles or {}
    rows = []
    now = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)
    for name, gdf in layers.items():
        gdf = gdf.copy()
        if gdf.crs is None:
            gdf = gdf.set_crs(4326)
        gdf = gdf.rename_geometry(GEOM_COL) if gdf.geometry.name != GEOM_COL else gdf
        pyogrio.write_dataframe(
            gdf, path, layer=name, driver="GPKG", promote_to_multi=True,
            append=path.exists(),
        )
        style = styles.get(name, style_for(name))
        rows.append({
            "f_table_catalog": "",
            "f_table_schema": "",
            "f_table_name": name,
            "f_geometry_column": GEOM_COL,
            "styleName": style,
            "styleQML": (ESTILOS / f"{style}.qml").read_text(encoding="utf-8"),
            "styleSLD": (ESTILOS / f"{style}.sld").read_text(encoding="utf-8"),
            "useAsDefault": True,
            "description": f"CacaoResiliente · {style}",
            "owner": "",
            "ui": "",
            "update_time": now,
        })
    # Tabla de estilos con el mismo esquema que crea QGIS (capa sin geometría).
    pyogrio.write_dataframe(pd.DataFrame(rows), path, layer="layer_styles", driver="GPKG", append=True)

    if descriptions:
        with sqlite3.connect(path) as con:
            for name, text in descriptions.items():
                con.execute("UPDATE gpkg_contents SET description = ? WHERE table_name = ?", (text, name))
    return path


def _cli(argv: list[str]) -> None:
    if len(argv) < 3:
        print(__doc__)
        sys.exit(1)
    out, specs = argv[1], argv[2:]
    layers = {}
    for spec in specs:
        name, src = spec.split("=", 1)
        layers[name] = gpd.read_file(src)
    p = write_styled_gpkg(layers, out)
    print(f"Escrito {p} con {len(layers)} capa(s) y estilos por defecto para QGIS.")


if __name__ == "__main__":
    _cli(sys.argv)
