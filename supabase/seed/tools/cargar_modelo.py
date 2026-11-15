"""Carga el modelo de ML en Supabase: migración 0010 + parte 13 (predicciones), en UNA transacción.

Si la base no tiene las zonas 2050, aplica también la parte 10 (NASA NEX-GDDP-CMIP6: clima, riesgo,
aptitud y zonas 2050). La lee de supabase/seed/data/ o, si no está en esta rama, de la rama
origin/diego/supabase-docs con `git show` (sin tocar los archivos).

    venv/bin/python supabase/seed/tools/cargar_modelo.py --dry-run   # prueba y deshace (no cambia nada)
    venv/bin/python supabase/seed/tools/cargar_modelo.py             # carga de verdad

Conexión: SUPABASE_DB_URL (variable de entorno, BACK/.env o supabase/seed/.env), la misma que usa
inject.py: Supabase → Project Settings → Database → Connection string → "Session pooler".
Requiere psycopg:  pip install "psycopg[binary]"

Es idempotente: se puede correr de nuevo (reemplaza las predicciones de ese modelo).
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
MIGRATION = ROOT / "supabase/migrations/0010_modelo_ml.sql"
DATA = ROOT / "supabase/seed/data/13_predicciones_modelo.sql"
AMAZONIA = ROOT / "supabase/seed/data/14_predicciones_amazonia.sql"  # extrapolación, va después de la 13
PART10 = "supabase/seed/data/10_proyecciones_2050.sql"
PART10_BRANCH = "origin/diego/supabase-docs"


def part10() -> str | None:
    f = ROOT / PART10
    if f.exists():
        return f.read_text(encoding="utf-8")
    import subprocess
    r = subprocess.run(["git", "-C", str(ROOT), "show", f"{PART10_BRANCH}:{PART10}"], capture_output=True, text=True)
    return r.stdout if r.returncode == 0 and r.stdout else None


def db_url() -> str | None:
    if os.environ.get("SUPABASE_DB_URL"):
        return os.environ["SUPABASE_DB_URL"]
    for env in (ROOT / "BACK/.env", ROOT / "supabase/seed/.env"):
        if env.exists():
            for line in env.read_text(encoding="utf-8").splitlines():
                if line.startswith("SUPABASE_DB_URL="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def body(src: Path | str) -> str:
    """Quita begin/commit del archivo: la transacción la maneja este script."""
    text = src.read_text(encoding="utf-8") if isinstance(src, Path) else src
    return "\n".join(l for l in text.splitlines() if l.strip().lower() not in ("begin;", "commit;"))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="ejecuta todo y deshace al final")
    ap.add_argument("--sin-2050", action="store_true", help="no aplicar la parte 10 aunque falten las zonas 2050")
    a = ap.parse_args()
    url = db_url()
    if not url:
        print("Falta SUPABASE_DB_URL (ver el encabezado de este script).")
        return 1
    try:
        import psycopg
    except ImportError:
        print('Falta psycopg:  pip install "psycopg[binary]"')
        return 1

    with psycopg.connect(url, autocommit=False, connect_timeout=20) as conn, conn.cursor() as cur:
        print(f"→ {MIGRATION.name}")
        cur.execute(body(MIGRATION))
        print(f"→ {DATA.name}")
        cur.execute(body(DATA))
        if AMAZONIA.exists():
            print(f"→ {AMAZONIA.name} (Amazonía: extrapolación desde Sucumbíos)")
            cur.execute(body(AMAZONIA))
        cur.execute("select count(*) from public.zone_classification")
        if cur.fetchone()[0] == 0 and not a.sin_2050:
            p10 = part10()
            if p10:
                print(f"→ 10_proyecciones_2050.sql (zonas, clima, riesgo y aptitud 2050; no estaban en la base)")
                cur.execute(body(p10))
            else:
                print(f"  ⚠ no encontré la parte 10 ni en {PART10} ni en {PART10_BRANCH} (haga git fetch)")
        cur.execute("""select scenario_id, count(*) filter (where kind = 'province'), count(*) filter (where kind = 'canton'),
                              round(avg(loss_pct) filter (where kind = 'country'), 1)
                         from public.v_loss_map where crop_id = 'cacao' group by 1 order by 1""")
        print("\n  escenario       provincias  cantones  % nacional")
        for sc, p, c, nat in cur.fetchall():
            print(f"  {sc:14} {p:>11} {c:>9} {nat if nat is not None else '—':>11}")
        cur.execute("select name from public.model_versions where crop_id = 'cacao' and is_active")
        print("\n  modelo activo:", ", ".join(r[0] for r in cur.fetchall()))
        cur.execute("select future_scenario_id, count(*) from public.zone_classification group by 1 order by 1")
        z = cur.fetchall()
        print("  zonas 2050:", ", ".join(f"{f} {n}" for f, n in z) if z else
              "VACÍAS → cargar la parte 10: python supabase/seed/inject.py --only 10")
        if a.dry_run:
            conn.rollback()
            print("\nPrueba OK. No se guardó nada (--dry-run).")
        else:
            conn.commit()
            print("\nListo: guardado en Supabase. Reinicia el backend para vaciar su caché.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
