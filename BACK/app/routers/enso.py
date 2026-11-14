"""El Niño: estado actual, historia y eventos."""
from fastapi import APIRouter, Query

from ..data import get_source
from ..services import enso

router = APIRouter(prefix="/enso", tags=["El Niño"])


def _month(v: str | None, end: bool = False) -> str | None:
    if not v:
        return None
    return v if len(v) == 10 else f"{v}-01" if len(v) == 7 else (f"{v}-12-01" if end else f"{v}-01-01")


@router.get("/current", summary="Fase ENSO actual (banner)")
def current():
    return enso.current()


@router.get("/history", summary="Series ONI / Niño 1+2 para gráficos")
def history(index: str = Query("oni,nino12_anom", description="oni, nino12_anom (separados por coma)"),
            date_from: str | None = Query("1990-01", alias="from"), date_to: str | None = Query(None, alias="to")):
    ids = [i.strip() for i in index.split(",") if i.strip() in {"oni", "nino12_anom", "nino34_anom"}]
    return enso.history(ids or ["oni"], _month(date_from), _month(date_to, end=True))


@router.get("/events", summary="Eventos Niño / Niña identificados")
def events(phase: str | None = Query(None, pattern="^(nino|nina)$"), date_from: int | None = Query(None, alias="from")):
    return [e for e in get_source().enso_events()
            if (not phase or e["phase"] == phase) and (not date_from or int(str(e["start_month"])[:4]) >= date_from)]


@router.get("/years", summary="Clasificación de cada año (Niño / Niña / neutral)")
def years():
    return enso.years()
