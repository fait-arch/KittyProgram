"""Inyecta el seed de pruebas en Supabase (Postgres).

Requisitos:   pip install -r supabase/seed/requirements.txt
Conexión:     variable SUPABASE_DB_URL (o archivo .env junto a este script / en BACK/.env)
              Supabase → Project Settings → Database → Connection string → "Session pooler"
              postgresql://postgres.<ref>:<PASSWORD>@aws-0-<region>.pooler.supabase.com:5432/postgres

Uso:
  python inject.py                  # carga las 6 partes (aborta si ya hay datos del seed)
  python inject.py --reset          # borra lo del seed y vuelve a cargar
  python inject.py --only 2,5       # solo algunas partes (01..06)
  python inject.py --verify         # solo muestra conteos
  python inject.py --dry-run        # revisa archivos y muestra qué haría, sin conectar
  python inject.py --reset-only     # solo borra el seed

Cada parte corre en su propia transacción: si falla, esa parte se deshace completa.
Orden obligatorio: 01 territorio → 02 El Niño → 03 clima → 04 riesgo → 05 producción → 06 modelo.
"""
import argparse
import os
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PARTS = {
    1: "01_territorio.sql", 2: "02_el_nino.sql", 3: "03_clima.sql",
    4: "04_riesgo_y_escenarios.sql", 5: "05_produccion_y_precios.sql", 6: "06_modelo_demo_y_observaciones.sql",
}
COUNT_TABLES = [
    "areas", "area_static_features", "enso_index", "enso_events", "area_monthly_series", "area_monthly_hazard",
    "disease_risk_monthly", "area_scenario_climate", "disease_risk_scenario", "crop_suitability",
    "crop_production_stats", "crop_exposure", "crop_prices", "model_versions", "loss_predictions",
    "field_observations", "etl_runs",
]
COUNTRY_ID = "df5013ea-246f-56b5-a845-683e6137e956"

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_env() -> str | None:
    if os.environ.get("SUPABASE_DB_URL"):
        return os.environ["SUPABASE_DB_URL"]
    for p in (HERE / ".env", HERE.parent.parent / "BACK" / ".env", HERE.parent.parent / ".env"):
        if p.exists():
            for line in p.read_text(encoding="utf-8").splitlines():
                if line.startswith("SUPABASE_DB_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def seed_area_ids() -> list[str]:
    txt = (DATA / PARTS[1]).read_text(encoding="utf-8")
    return re.findall(r"^\('([0-9a-f-]{36})','(?:country|province|canton)'", txt, re.M)


def reset_sql(ids: list[str]) -> list[str]:
    arr = "'{" + ",".join(ids) + "}'::uuid[]"
    return [
        "delete from public.loss_predictions where model_version_id in (select id from public.model_versions where name like 'cacao_loss_demo%')",
        "delete from public.model_versions where name like 'cacao_loss_demo%'",
        "delete from public.field_observations where source = 'gbif'",
        "delete from public.etl_runs where script = 'seed_pruebas'",
        "delete from public.crop_prices where source_id = 'fred'",
        "delete from public.enso_events",
        "delete from public.enso_index",
        f"delete from public.areas where id = any({arr}) and not exists (select 1 from public.areas f where f.kind = 'field' and f.parent_id = any({arr}))",
    ]


def counts(cur) -> dict[str, int]:
    out = {}
    for t in COUNT_TABLES:
        cur.execute(f"select count(*) from public.{t}")
        out[t] = cur.fetchone()[0]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--reset", action="store_true", help="borra el seed antes de cargar")
    ap.add_argument("--reset-only", action="store_true", help="solo borra el seed")
    ap.add_argument("--only", help="partes a cargar, p. ej. 1,2,3")
    ap.add_argument("--verify", action="store_true", help="solo muestra conteos")
    ap.add_argument("--dry-run", action="store_true", help="no conecta; revisa archivos")
    ap.add_argument("--yes", action="store_true", help="no pedir confirmación")
    a = ap.parse_args()

    only = [int(x) for x in a.only.split(",")] if a.only else sorted(PARTS)
    files = {n: DATA / PARTS[n] for n in only}
    missing = [str(p) for p in files.values() if not p.exists()]
    if missing and not a.verify:
        print("Faltan archivos:", *missing, sep="\n  ")
        print("Genera los datos con supabase/seed/tools/build_seed.py (ver README).")
        return 1

    if a.dry_run:
        print("DRY-RUN — no se conecta a ninguna base.")
        for n, p in files.items():
            sql = p.read_text(encoding="utf-8")
            print(f"  parte {n:02d}  {p.name:42s} {len(sql)/1024:8,.0f} KB  {sql.count('insert into'):3d} sentencias insert")
        ids = seed_area_ids()
        print(f"  áreas del seed (para --reset): {len(ids)}")
        return 0

    url = load_env()
    if not url:
        print("Falta SUPABASE_DB_URL (ver encabezado de este script).")
        return 1
    try:
        import psycopg
    except ImportError:
        print("Falta psycopg:  pip install -r supabase/seed/requirements.txt")
        return 1

    host = re.sub(r"^.*@", "", url).split("/")[0]
    print(f"Conectando a {host} …")
    try:
        conn_ctx = psycopg.connect(url, autocommit=False, connect_timeout=20)
    except psycopg.OperationalError as e:
        msg = str(e)
        print("No se pudo conectar:", msg.splitlines()[0][-110:])
        if "password authentication failed" in msg:
            print("La contraseña de SUPABASE_DB_URL es incorrecta: resetéala en Project Settings → Database y actualiza el .env.")
        return 3
    with conn_ctx as conn:
        cur = conn.cursor()
        cur.execute("select current_database(), count(*) from public.areas where id = %s", (COUNTRY_ID,))
        dbname, seeded = cur.fetchone()
        conn.rollback()

        if a.verify:
            for t, n in counts(cur).items():
                print(f"  {t:26s} {n:>8,}")
            return 0

        if (a.reset or a.reset_only) and not a.yes:
            r = input(f"Se borrará el seed en «{dbname}» ({host}). Escribe SI para continuar: ")
            if r.strip().upper() != "SI":
                print("Cancelado.")
                return 1

        if a.reset or a.reset_only:
            t0 = time.time()
            for s in reset_sql(seed_area_ids()):
                cur.execute(s)
                print(f"  reset: {s[:70]:70s} {cur.rowcount:>8,} filas")
            conn.commit()
            print(f"Seed borrado en {time.time()-t0:.1f}s")
            if a.reset_only:
                return 0
        elif seeded and 1 in only:
            print("Ya hay datos del seed (país Ecuador cargado). Usa --reset para recargar o --only para otras partes.")
            return 1

        for n, p in files.items():
            sql = p.read_text(encoding="utf-8")
            t0 = time.time()
            try:
                cur.execute(sql)
                conn.commit()
                print(f"  parte {n:02d} OK   {p.name:42s} {time.time()-t0:6.1f}s")
            except Exception as e:  # la parte se deshace completa
                conn.rollback()
                print(f"  parte {n:02d} ERROR {p.name}: {str(e).splitlines()[0]}")
                print("  Se detiene aquí. Corrige y relanza con --reset.")
                return 2

        print("\nConteos finales:")
        for t, c in counts(cur).items():
            print(f"  {t:26s} {c:>8,}")
        print("\nListo. Prueba el mapa:  select name, scenario_id, loss_pct, risk_class from public.v_loss_map limit 10;")
    return 0


if __name__ == "__main__":
    sys.exit(main())
