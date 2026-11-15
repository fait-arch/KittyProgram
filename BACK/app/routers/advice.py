"""Estrategias, what-if del modelo e insights de IA."""
from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, Field

from ..services import alerts, climate, insights, predictor, strategies, territory

router = APIRouter(tags=["recomendaciones"])


@router.get("/areas/{area_id}/strategies", summary="Estrategias evaluadas (≥ 3 + la actual), reordenables por prioridades")
def area_strategies(area_id: str, scenario: str = "nino", crop: str = "cacao", priorities: str | None = None):
    """`priorities` = `ingreso:5,costo:3,suelo:2,agua:4,mano_obra:1` (0–5). Sin prioridades → por beneficio neto."""
    climate.check_scenario(scenario)
    return strategies.evaluate(area_id, crop, scenario, strategies.parse_priorities(priorities))


@router.get("/alerts", summary="Alertas en lenguaje natural por provincia (hechos del modelo, redacción con IA)")
def area_alerts(scenario: str = "actual", province: str | None = None, crop: str = "cacao"):
    climate.check_scenario(scenario)
    return alerts.build(crop, scenario, province or None)


@router.get("/areas/{area_id}/insights", summary="Insights y recomendaciones generadas por IA (Claude)")
def area_insights(area_id: str, scenario: str = "nino", crop: str = "cacao", priorities: str | None = None):
    climate.check_scenario(scenario)
    territory.get_area(area_id)
    pri = strategies.parse_priorities(priorities)
    return insights.insights(area_id, crop, scenario, tuple(sorted(pri.items())))


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., max_length=4000)


class AskBody(BaseModel):
    question: str = Field(..., min_length=3, max_length=1000)
    scenario: str = "nino"
    crop: str = "cacao"
    history: list[Turn] = Field(default_factory=list, max_length=20)


@router.post("/areas/{area_id}/ask", summary="Pregunta libre a la IA sobre el cantón")
def area_ask(area_id: str, body: AskBody):
    climate.check_scenario(body.scenario)
    territory.get_area(area_id)
    return insights.ask(area_id, body.crop, body.scenario, body.question, [t.model_dump() for t in body.history])


class Adjust(BaseModel):
    temp_delta_c: float | None = Field(None, description="°C a sumar (−3…+4)")
    rain_delta_pct: float | None = Field(None, description="% de lluvia (−50…+100)")
    nino12_anom: float | None = Field(None, description="Anomalía Niño 1+2 en °C")
    oni: float | None = None


class PredictBody(BaseModel):
    area_id: str
    crop: str = "cacao"
    base_scenario: str = "normal"
    adjust: Adjust = Field(default_factory=Adjust)


@router.post("/predict", summary="What-if: pérdida con lluvia/temperatura/Niño ajustados (modelo en memoria)")
def predict(body: PredictBody):
    climate.check_scenario(body.base_scenario)
    return predictor.what_if(body.area_id, body.crop, body.base_scenario, body.adjust.model_dump())
