"""Textos en lenguaje de agricultor. Si ML agrega una feature, se agrega aquí."""

DISCLAIMER = ("Estimación con datos satelitales y estadísticos. Apoya, no reemplaza, el criterio del "
              "agricultor: validar con técnicos del INIAP/MAG antes de decidir.")

ATTRIBUTION = ("NASA (GPM IMERG, SMAP, MODIS, SRTM, NEX-GDDP-CMIP6, POWER, ECOSTRESS) · Contains modified "
               "Copernicus Climate Change Service information (ERA5-Land) · NOAA CPC · INEC (ESPAC) · "
               "FAO (FAOSTAT, ECOCROP, GAUL) · MAG (SIPA) · GBIF.org")

LIMITATIONS = [
    "Pocas observaciones para entrenar (≈140 provincia-año): los intervalos son amplios.",
    "El rendimiento cae por muchas causas (precio, manejo, plagas no climáticas); el modelo solo capta la parte asociada al clima.",
    "Los umbrales de enfermedad son referenciales de literatura y aún no están validados en campo.",
    "El modelo se entrena por provincia y se aplica por cantón.",
    "Los escenarios 2050 extrapolan fuera del clima observado.",
]

PARAMETERS = {
    "temp_mean": "Temperatura media", "rain_annual": "Lluvia anual", "ph": "pH del suelo",
    "altitude": "Altitud", "killing_temp": "Temperatura mínima letal", "growth_days": "Ciclo",
    "light": "Luz", "soil_depth": "Profundidad del suelo", "soil_texture": "Textura del suelo", "drainage": "Drenaje",
}

FEATURES = {
    "fav_days_monilia": ("Días muy húmedos que favorecen la moniliasis (ene–jun)", "días"),
    "fav_days_phytophthora": ("Días de lluvia y humedad que favorecen la mazorca negra (ene–jun)", "días"),
    "fav_days_escoba": ("Días húmedos que favorecen la escoba de bruja (ene–jun)", "días"),
    "heavy_rain_days": ("Días de aguacero (> 50 mm)", "días"),
    "saturated_days": ("Días con el suelo encharcado (ene–jun)", "días"),
    "evi_jan_jun": ("Verdor del cultivo medido por satélite (MODIS)", "EVI"),
    "price_vs3_prev": ("Precio del año anterior frente a los 3 previos", "%"),
    "humid_days": ("Días con humedad del aire ≥ 80 %", "días"),
    "precip_total_mm": ("Lluvia total en la época de riesgo", "mm"),
    "risk_index_mean": ("Riesgo climático de enfermedad promedio", "0–1"),
    "nino12_anom_jan_jun": ("Calentamiento del mar frente a Ecuador", "°C"),
    "oni_jan_jun": ("Intensidad de El Niño en el Pacífico", "°C"),
    "suitability_now": ("Qué tan apto es el clima para el cacao", "0–1"),
    "rain_total_vs_opt": ("Lluvia por encima de lo que el cacao necesita", "mm"),
    "yield_anom_prev": ("Cómo le fue a la cosecha el año anterior", "%"),
    # nombres del paquete ml/ (rama de Arthur)
    "rain_total": ("Lluvia total ene–jun", "mm"), "rain_anom_pct": ("Lluvia ene–jun frente a lo normal", "%"),
    "rain_max_1d": ("Aguacero más fuerte del periodo", "mm"), "rain_max_5d": ("Lluvia máxima en 5 días seguidos", "mm"),
    "wet_days": ("Días con lluvia", "días"), "max_wet_spell": ("Racha más larga de días lluviosos", "días"),
    "rain_p95_days": ("Días de lluvia extrema para la zona", "días"), "rh_mean": ("Humedad del aire promedio", "%"),
    "t_mean": ("Temperatura media", "°C"), "tmax_mean": ("Temperatura máxima media", "°C"),
    "tmin_mean": ("Temperatura mínima media", "°C"), "et0_total": ("Agua que pide la atmósfera (ET₀)", "mm"),
    "solar_mean": ("Radiación solar", "MJ/m²"), "water_balance": ("Balance de agua (lluvia − ET₀)", "mm"),
    "suitability": ("Qué tan apto es el clima para el cacao", "0–1"),
    "rain_excess_opt": ("Lluvia por encima de lo que el cacao necesita", "mm"),
    "rain_prev_ond": ("Lluvia de oct–dic del año anterior", "mm"),
    "fav_phyto_prev_ond": ("Días favorables a mazorca negra en oct–dic previo", "días"),
    "nino12_jan_jun": ("Calentamiento del mar frente a Ecuador", "°C"), "nino34_jan_jun": ("El Niño en el Pacífico central (Niño 3.4)", "°C"),
    "oni_djf": ("El Niño en dic–feb", "°C"), "nino12_prev_ond": ("Mar frente a Ecuador en oct–dic previo", "°C"),
    "y_anom_prev": ("Cómo le fue a la cosecha el año anterior", "%"),
}

VARIABLE_OPS = {  # cómo se resume el año: suma o promedio
    "precip": "sum", "heavy_rain_days": "sum", "wet_days": "sum", "saturated_days": "sum", "hot_days": "sum",
    "humid_days": "sum", "et0": "sum", "et_actual": "sum", "water_balance": "sum",
}

STRATEGY_TARGET_LABELS = {
    "monilia": "moniliasis", "phytophthora": "mazorca negra", "escoba_bruja": "escoba de bruja",
    "encharcamiento": "encharcamiento", "calor": "estrés por calor", "ingreso": "ingreso del productor",
}

RISK_CLASSES = [{"id": "bajo", "max": 5}, {"id": "medio", "max": 15}, {"id": "alto", "max": 30}, {"id": "muy_alto", "max": 100}]

VAR_TEXT = {"rh_mean": "la humedad del aire", "t2m": "la temperatura", "precip": "la lluvia del día"}


def feature_label(f: str) -> str:
    return FEATURES.get(f, (f, ""))[0]


def risk_class(loss_pct: float | None) -> str | None:
    if loss_pct is None:
        return None
    for c in RISK_CLASSES:
        if loss_pct < c["max"]:
            return c["id"]
    return "muy_alto"


def rule_text(thresholds: list[dict]) -> str:
    parts = []
    for t in thresholds:
        name = VAR_TEXT.get(t["variable_id"], t["variable_id"])
        mn, mx, u = t.get("min_value"), t.get("max_value"), t.get("unit") or ""
        if mn is not None and mx is not None:
            parts.append(f"{name} entre {mn:g} y {mx:g} {u}".strip())
        elif mn is not None:
            parts.append(f"{name} ≥ {mn:g} {u}".strip())
        elif mx is not None:
            parts.append(f"{name} ≤ {mx:g} {u}".strip())
    return (" y ".join(parts)).capitalize() if parts else ""
