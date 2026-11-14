"""Áreas, provincias, GeoJSON y búsqueda de cantón por punto (sin RPC: shapely en memoria)."""
from shapely.geometry import Point, shape
from shapely.strtree import STRtree

from ..core.cache import cached
from ..core.errors import bad_request, not_found
from ..data import get_source
from ..data.common import is_uuid


@cached(ttl=24 * 3600)
def province_index() -> dict[str, dict]:
    return {p["id"]: p for p in get_source().areas(kind="province")}


def resolve_province(value: str | None) -> dict | None:
    """Acepta uuid o nombre (con o sin tildes). None si no se pidió."""
    if not value:
        return None
    if is_uuid(value):
        p = province_index().get(value)
    else:
        p = get_source().find_area("province", value)
    if not p:
        raise not_found("province_not_found", f"Provincia no encontrada: {value}")
    return p


def get_area(area_id: str) -> dict:
    if not is_uuid(area_id):
        raise bad_request("invalid_area_id", "area_id debe ser un uuid")
    a = get_source().area(area_id)
    if not a:
        raise not_found("area_not_found", "Área no encontrada")
    prov = province_index().get(a.get("parent_id") or "")
    a["province"] = {"id": prov["id"], "name": prov["name"]} if prov else None
    return a


@cached(ttl=24 * 3600)
def geometries(kind: str, parent_id: str | None = None) -> list[dict]:
    return get_source().areas_geom(kind, parent_id)


def feature_collection(kind: str, parent_id: str | None = None, extra: dict[str, dict] | None = None) -> dict:
    provs = province_index()
    feats = []
    for g in geometries(kind, parent_id):
        if not g.get("geom"):
            continue
        props = {"id": g["id"], "name": g["name"], "kind": g["kind"],
                 "province": provs.get(g.get("parent_id") or "", {}).get("name")}
        if extra is not None:
            if g["id"] not in extra:
                continue
            props.update(extra[g["id"]])
        feats.append({"type": "Feature", "id": g["id"], "properties": props, "geometry": g["geom"]})
    return {"type": "FeatureCollection", "features": feats}


@cached(ttl=24 * 3600)
def _canton_tree() -> tuple[STRtree, list[dict], list]:
    items = [g for g in geometries("canton") if g.get("geom")]
    shapes = [shape(g["geom"]) for g in items]
    return STRtree(shapes), items, shapes


def lookup(lat: float, lon: float) -> dict | None:
    if not (-6 <= lat <= 2.5 and -92.5 <= lon <= -74.5):
        raise bad_request("outside_ecuador", "El punto está fuera de Ecuador")
    tree, items, shapes = _canton_tree()
    pt = Point(lon, lat)
    for i in tree.query(pt):
        if shapes[i].contains(pt):
            g = items[i]
            prov = province_index().get(g.get("parent_id") or "")
            return {"canton": {"id": g["id"], "name": g["name"]},
                    "province": {"id": prov["id"], "name": prov["name"]} if prov else None}
    return None


def centroid(area_id: str) -> dict | None:
    for kind in ("canton", "province"):
        for g in geometries(kind):
            if g["id"] == area_id and g.get("geom"):
                c = shape(g["geom"]).centroid
                return {"lat": round(c.y, 4), "lon": round(c.x, 4)}
    return None
