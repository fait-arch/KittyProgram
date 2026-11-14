# Exportación compatible con QGIS

La app y QGIS usan **la misma leyenda**: símbolo graduado sobre `loss_pct`, rampa
**ColorBrewer YlOrRd de 4 clases** (de amarillo a rojo) y borde gris oscuro como el de QGIS.

| Clase | Rango `loss_pct` | Color |
|-------|------------------|-------|
| Baja | 0 – 5 % | `#ffffb2` |
| Moderada | 5 – 15 % | `#fecc5c` |
| Alta | 15 – 30 % | `#fd8d3c` |
| Muy alta | 30 – 100 % | `#e31a1c` |

Borde: `#232323`, 0,26 mm (el de QGIS por defecto). El límite superior de cada clase es
**inclusivo**, como hace QGIS: 5,0 % cae en "Baja". La app clasifica igual.

## Contenido

| Ruta | Qué es |
|------|--------|
| `estilos/perdida_cacao.qml` | Estilo QGIS (graduado, YlOrRd 4 clases) para las capas de pérdida |
| `estilos/perdida_cacao.sld` | El mismo estilo en SLD 1.1, para GeoServer u otros SIG |
| `estilos/zonas_2050.qml` / `.sld` | Estilo categorizado de la matriz de zonas 2050 (`zona_2050`) |
| `datos/cacao_perdida_EJEMPLO.gpkg` | GeoPackage de ejemplo: 6 capas con su estilo incluido. **Datos ilustrativos.** |
| `exportar_gpkg.py` | Función `write_styled_gpkg()` para que el backend genere el mismo GeoPackage con datos reales |

## Abrir en QGIS

1. **GeoPackage (recomendado):** arrastrar `cacao_perdida_EJEMPLO.gpkg` a QGIS y elegir las capas.
   Cada capa abre con su leyenda, porque el estilo está guardado en la tabla `layer_styles`
   (el mismo mecanismo que usa QGIS al hacer *Guardar estilo › En la base de datos*).
2. **GeoJSON o Shapefile:** *Propiedades de la capa › Simbología › Estilo › Cargar estilo…* y elegir
   `estilos/perdida_cacao.qml`. Si el `.qml` tiene el mismo nombre que el archivo de datos
   (p. ej. `perdida_nino.shp` + `perdida_nino.qml`), QGIS lo aplica solo al abrir la capa.
3. **A mano:** Simbología › *Graduado* › Valor `loss_pct` › Rampa *ColorBrewer › YlOrRd*, 4 clases ›
   editar los límites a 0, 5, 15, 30 y 100.

Los estilos usan el formato de QGIS 3.34 LTR e incluyen las propiedades en el formato
anterior (`<prop>`) para versiones 3.x más viejas. Se validaron como XML y el GeoPackage se
leyó con GDAL; falta probarlos abriéndolos en QGIS.

## Capas y campos

Capas del GeoPackage: `perdida_normal`, `perdida_nino`, `perdida_actual`,
`perdida_ssp245_2050`, `perdida_ssp585_2050` y `zonas_2050`.

| Campo | Tipo | Contenido |
|-------|------|-----------|
| `canton` | texto | Nombre del cantón |
| `provincia` | texto | Provincia |
| `escenario` | texto | `normal` · `nino` · `actual` · `ssp245_2050` · `ssp585_2050` |
| `loss_pct` | real | Pérdida estimada (%) — campo de la simbología |
| `loss_p10` / `loss_p90` | real | Rango probable |
| `clase` | texto | `baja` · `moderada` · `alta` · `muy_alta` |
| `zona_2050` | texto | `segura` · `manejo` · `transicion` · `critica` |
| `fuente` | texto | Modelo, versión y fecha (en el ejemplo: "EJEMPLO ILUSTRATIVO") |

Nombres de 10 caracteres o menos, para que también sirvan en Shapefile.

**Sistema de referencia:** EPSG:4326 (WGS 84). Para medir áreas o maquetar con escala exacta,
reproyectar a **EPSG:32717 (WGS 84 / UTM 17S)**, que cubre la Costa.

## Composición de mapa (patrón QGIS)

Para láminas e informes, la composición de impresión lleva: título y escenario, leyenda
"Pérdida estimada (%)", escala gráfica en km, flecha norte, grilla de coordenadas, SRC,
fuentes de datos (NASA GPM, SMAP, MODIS, SRTM, NEX-GDDP-CMIP6; Copernicus ERA5-Land; NOAA;
INEC; FAO) y la nota "Estimación: validar con INIAP/MAG". La pantalla del mapa de la app
sigue el mismo patrón.

## Backend: endpoint de exportación

```
GET /api/v1/export?scenarios=nino,normal&format=gpkg|geojson|shp|sld&crs=4326|32717&level=canton
```

- `gpkg`: `write_styled_gpkg({...}, ruta)` → un archivo con todas las capas y sus estilos.
- `geojson` / `shp`: `.zip` con los datos + un `.qml` con el mismo nombre de cada capa.
- `sld`: solo `estilos/perdida_cacao.sld`.

```python
from exportar_gpkg import write_styled_gpkg
write_styled_gpkg({"perdida_nino": gdf_nino}, "/tmp/cacao.gpkg",
                  descriptions={"perdida_nino": "Pérdida estimada · Año Niño · cacao_loss_v1"})
```

Requiere `geopandas` y `pyogrio`.

## Origen de las geometrías del ejemplo

Límites cantonales de [pabl-o-ce/ecuador-geojson](https://github.com/pabl-o-ce/ecuador-geojson)
(MIT License, © 2020 Pablo Carrera Estrada), simplificados para el ejemplo. En producción
vienen de `/areas/geojson` (FAO GAUL).
