"""ESPAC (INEC) real por provincia → CSV local + SQL de inyección para Supabase.

URLs de descarga (INEC): ver ESPAC_URLS en ml/etl/production.py (rama beltranfuego).

Lee los tabulados anuales de la ESPAC (2002–2025), tabla "Superficie, producción y ventas,
según región y provincia — cacao (almendra seca)" (T13 en 2002–2015, T14 desde 2016), suma las
filas "Solo" + "Asociado" de cada provincia y controla que las provincias sumen el total
nacional (±2 %). El lector sigue la lógica de ml/etl/production.py (rama beltranfuego).

    python -I supabase/seed/tools/espac_to_sql.py supabase/seed/raw/espac supabase/seed/data

Salidas:
  <raw>/espac_cacao_provincias.csv     todas las provincias y años (incluye las no cargadas en areas)
  <data>/07_espac_real.sql             upsert en crop_production_stats (source_id = 'espac') y
                                       borrado de las filas sintéticas del mismo área × año.

El SQL NO se ejecuta aquí. Se aplica con `python supabase/seed/inject.py --only 7` o pegándolo en el SQL Editor.
Las provincias se cruzan por inec_dpa_code: las que no existan en public.areas se omiten solas.
"""
import csv
import re
import sys
import unicodedata
from pathlib import Path

import openpyxl

RAW = Path(sys.argv[1])
OUT = Path(sys.argv[2])
YEARS = range(2002, 2026)
TOL = 0.02

# Códigos DPA del INEC (provincia, 2 dígitos)
DPA = {
    "azuay": "01", "bolivar": "02", "canar": "03", "carchi": "04", "cotopaxi": "05", "chimborazo": "06",
    "el oro": "07", "esmeraldas": "08", "guayas": "09", "imbabura": "10", "loja": "11", "los rios": "12",
    "manabi": "13", "morona santiago": "14", "napo": "15", "pastaza": "16", "pichincha": "17",
    "tungurahua": "18", "zamora chinchipe": "19", "galapagos": "20", "sucumbios": "21", "orellana": "22",
    "santo domingo de los tsachilas": "23", "santo domingo": "23", "santa elena": "24",
}
MISSING = {".", "*", "-", "", "…", "..."}
NON_PROVINCE = re.compile(r"^(REGI[OÓ]N|ZONAS? NO DELIMITADAS?|NORORIENTE|CENTRO-SURORIENTE|TOTAL|FUENTE|NOTA)", re.I)
# Agregados que SÍ suman al total nacional pero no son provincias: Amazonía 2002–2011 publicada
# por subregión, y zonas no delimitadas (2014–2015). Se usan solo para el control de cuadre.
AGGREGATE = re.compile(r"^(ZONAS? NO DELIMITADAS?|NORORIENTE|CENTRO-SURORIENTE)", re.I)


def key(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s).strip().lower()


def num(v) -> tuple[float | None, bool]:
    """(valor, oculto). '*' = dato oculto por confidencialidad del INEC."""
    if v is None:
        return None, False
    if isinstance(v, (int, float)):
        return float(v), False
    s = str(v).strip()
    if s in MISSING:
        return None, s == "*"
    try:
        return float(s.replace(",", "")), False
    except ValueError:
        return None, False


def sheet_key(s: str) -> str:
    return re.sub(r"[\s.]", "", str(s)).upper()


def find_sheet(wb):
    by_key = {sheet_key(n): n for n in wb.sheetnames}
    for r in wb.worksheets[0].iter_rows(values_only=True):   # 1) índice del libro
        cells = [str(c) for c in r if c is not None]
        text = " ".join(cells)
        if not (re.search(r"cacao", text, re.I) and re.search(r"provincia", text, re.I)):
            continue
        for c in cells:
            m = re.match(r"^\s*(?:TABLA\s*)?(T\s*\d+)\b", c, re.I)
            if m and sheet_key(m.group(1)) in by_key:
                return wb[by_key[sheet_key(m.group(1))]]
    for ws in wb.worksheets:                                 # 2) título dentro de la hoja
        if not re.match(r"^T\s*\d+\.?$", ws.title.strip()):
            continue
        head = " ".join(str(c) for r in ws.iter_rows(max_row=8, values_only=True) for c in r if c)
        if re.search(r"cacao", head, re.I) and re.search(r"provincia", head, re.I):
            return ws
    raise ValueError("no se encontró la tabla de cacao por provincia")


def parse(path: Path) -> tuple[dict, list | None, str, dict]:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = find_sheet(wb)
    title = ws.title
    rows = [list(r) for r in ws.iter_rows(values_only=True)]
    wb.close()
    c0 = next(i for r in rows for i, v in enumerate(r) if isinstance(v, str) and v.strip() == "Plantada")
    recs: dict[str, dict] = {}
    agg: dict[str, float] = {}          # producción de agregados no provinciales (Solo + Asociado)
    agg_summary: dict[str, float] = {}  # mismos agregados en el bloque de resumen (sin Solo/Asociado)
    national, current, cur_agg = None, None, None
    for r in rows:
        strs = [s.strip() for s in r[:c0] if isinstance(s, str) and s.strip()]
        label = next((s for s in strs if s not in ("Solo", "Asociado")), None)
        kind = next((s for s in strs if s in ("Solo", "Asociado")), None)
        vals = [num(v) for v in (r[c0:c0 + 4] + [None] * 4)[:4]]   # plantada, cosechada, producción, ventas
        if label and label.upper().startswith("TOTAL NACIONAL") and national is None:
            national = [v for v, _ in vals]
            continue
        if kind == "Solo" and label:
            current = None if NON_PROVINCE.match(label) else key(label)
            cur_agg = key(label) if AGGREGATE.match(label) else None
        elif kind is None:
            if label:
                current, cur_agg = None, None
                if AGGREGATE.match(label) and vals[2][0] is not None:
                    agg_summary[key(label)] = vals[2][0]
            continue
        if cur_agg is not None and vals[2][0] is not None:
            agg[cur_agg] = agg.get(cur_agg, 0.0) + vals[2][0]
        if current is None:
            continue
        rec = recs.setdefault(current, {"v": [None] * 4, "hidden": False, "label": label or current})
        for k, (x, hid) in enumerate(vals):
            if x is not None:
                rec["v"][k] = x if rec["v"][k] is None else rec["v"][k] + x
            rec["hidden"] |= hid
    return recs, national, title, {**agg_summary, **agg}


def lit(v) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, (int, float)):
        return repr(round(float(v), 3))
    return "'" + str(v).replace("'", "''") + "'"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    rows, nat_rows, report = [], [], []
    for y in YEARS:
        fp = RAW / f"espac_tab{y}.xlsx"
        if not fp.exists():
            report.append((y, "sin archivo", None, None, None))
            continue
        try:
            recs, national, sheet, agg = parse(fp)
        except Exception as e:  # noqa: BLE001
            report.append((y, f"ERROR: {e}", None, None, None))
            continue
        tot = sum(d["v"][2] or 0 for d in recs.values())
        agg_t = sum(agg.values())
        nat = (national or [None] * 4)[2]
        ok = bool(nat) and abs(tot + agg_t - nat) / nat < TOL
        note = f" +agregados {agg_t:,.0f} t" if agg_t else ""
        report.append((y, (f"OK ({sheet}){note}" if ok else f"NO CUADRA ({sheet}){note}"), nat, tot, len(recs)))
        for k, d in sorted(recs.items()):
            planted, harvested, prod, sold = d["v"]
            rows.append({"year": y, "province": d["label"], "name_key": k, "dpa": DPA.get(k),
                         "planted_ha": planted, "harvested_ha": harvested, "production_t": prod, "sales_t": sold,
                         "yield_t_ha": (prod / harvested) if prod and harvested else None,
                         "hidden_values": d["hidden"], "year_ok": ok, "sheet": sheet})
        if national:
            nat_rows.append({"year": y, "planted_ha": national[0], "harvested_ha": national[1],
                             "production_t": national[2], "year_ok": ok})

    csv_path = RAW / "espac_cacao_provincias.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    with open(RAW / "espac_cacao_nacional.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(nat_rows[0]))
        w.writeheader()
        w.writerows(nat_rows)

    good = [r for r in rows if r["year_ok"] and r["dpa"] and r["harvested_ha"]]
    good_nat = [r for r in nat_rows if r["year_ok"]]
    years_ok = sorted({r["year"] for r in good})
    pv = ",\n".join(f"({lit(r['dpa'])},{r['year']},{lit(r['planted_ha'])},{lit(r['harvested_ha'])},{lit(r['production_t'])},"
                    f"{lit(f'ESPAC {r[chr(121)+chr(101)+chr(97)+chr(114)]} {r[chr(115)+chr(104)+chr(101)+chr(101)+chr(116)]} (solo + asociado)' + (' · contiene valores ocultos por el INEC (*)' if r['hidden_values'] else ''))})"
                    for r in good)
    nv = ",\n".join(f"({r['year']},{lit(r['planted_ha'])},{lit(r['harvested_ha'])},{lit(r['production_t'])})" for r in good_nat)

    sql = f"""-- =====================================================================
--  07 — Producción REAL de cacao por provincia, ESPAC (INEC) {years_ok[0]}–{years_ok[-1]}
--  Generado por supabase/seed/tools/espac_to_sql.py. NO editar a mano.
--  Fuente: tabulados ESPAC, "Superficie, producción y ventas, según región y provincia —
--  cacao (almendra seca)", suma de cultivo solo + asociado. Años incluidos: {', '.join(map(str, years_ok))}
--  (solo años cuyas provincias + agregados no provinciales suman el total nacional ±{TOL:.0%}).
--  2002–2011: la Amazonía venía agregada (Nororiente / Centro-Suroriente) → sin filas por provincia amazónica.
--
--  Qué hace (en una transacción):
--    1. Borra las filas SINTÉTICAS (source_id = 'seed_sintetico') de las provincias × años
--       que ahora tienen dato real, para no duplicar el dataset de entrenamiento.
--    2. Inserta/actualiza las filas reales (source_id = 'espac').
--    3. Inserta/actualiza el total nacional ESPAC en el área 'country'.
--  Las provincias se cruzan por inec_dpa_code: las que no estén en public.areas se omiten.
--  Requiere: migraciones 0001–0009 y el seed 01_territorio (áreas con inec_dpa_code).
-- =====================================================================
begin;

create temporary table _espac (dpa text, year smallint, planted_ha numeric, harvested_ha numeric,
                               production_t numeric, notes text) on commit drop;
insert into _espac values
{pv};

create temporary table _espac_nat (year smallint, planted_ha numeric, harvested_ha numeric,
                                   production_t numeric) on commit drop;
insert into _espac_nat values
{nv};

-- 1. Quitar sintéticos reemplazados por dato real
delete from public.crop_production_stats s
 using _espac e, public.areas a
 where a.kind = 'province' and a.inec_dpa_code = e.dpa
   and s.area_id = a.id and s.year = e.year and s.crop_id = 'cacao'
   and s.source_id = 'seed_sintetico';

-- 2. Provincias (real)
insert into public.crop_production_stats
       (area_id, crop_id, year, planted_ha, productive_ha, harvested_ha, lost_ha, production_t, source_id, notes)
select a.id, 'cacao', e.year, e.planted_ha, null, e.harvested_ha, null, e.production_t, 'espac', e.notes
  from _espac e
  join public.areas a on a.kind = 'province' and a.inec_dpa_code = e.dpa
on conflict (area_id, crop_id, year, source_id) do update
   set planted_ha = excluded.planted_ha, harvested_ha = excluded.harvested_ha,
       production_t = excluded.production_t, notes = excluded.notes;

-- 3. Total nacional (real)
insert into public.crop_production_stats
       (area_id, crop_id, year, planted_ha, productive_ha, harvested_ha, lost_ha, production_t, source_id, notes)
select a.id, 'cacao', n.year, n.planted_ha, null, n.harvested_ha, null, n.production_t, 'espac',
       'ESPAC ' || n.year || ' total nacional (solo + asociado)'
  from _espac_nat n
  join public.areas a on a.kind = 'country'
on conflict (area_id, crop_id, year, source_id) do update
   set planted_ha = excluded.planted_ha, harvested_ha = excluded.harvested_ha,
       production_t = excluded.production_t, notes = excluded.notes;

commit;

-- Comprobar después:
--   select * from public.v_production_provenance where year between {years_ok[0]} and {years_ok[-1]} order by year;
"""
    (OUT / "07_espac_real.sql").write_text(sql, encoding="utf-8")

    print(f"{'año':>4}  {'estado':<44} {'nacional t':>12} {'suma prov t':>12} {'prov':>4}")
    for y, st, nat, tot, n in report:
        print(f"{y:>4}  {st:<44} {nat or 0:>12,.0f} {tot or 0:>12,.0f} {n or 0:>4}")
    print(f"\nCSV: {csv_path} ({len(rows)} filas)")
    print(f"SQL: {OUT / '07_espac_real.sql'} ({len(good)} filas provinciales en años OK, {len(good_nat)} nacionales)")
    unk = sorted({r['name_key'] for r in rows if not r['dpa']})
    if unk:
        print("Provincias sin código DPA (revisar):", unk)
    return 0


if __name__ == "__main__":
    sys.exit(main())
