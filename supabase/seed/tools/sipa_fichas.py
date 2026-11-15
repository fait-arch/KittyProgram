"""Precio al productor mensual de cacao (SIPA / MAG) desde las FICHAS DEL CULTIVO DE CACAO (PDF).

Las fichas se exportan a mano desde https://sipa.agricultura.gob.ec/index.php/cacao (una por año).
El gráfico "Precios USD Dólares - Precio Productor - <año>" trae los 12 valores impresos; se leen con
`pdftotext -bbox` y cada valor se asigna al mes cuya etiqueta (ENERO … DICIEMBRE) está más cerca en x.

    python -I sipa_fichas.py <carpeta_con_pdfs> <salida.csv>
Salida: month,usd_per_qq,source_file   (formato que lee build_seed.py como raw/sipa_cacao.csv)
"""
import csv
import html
import re
import subprocess
import sys
from pathlib import Path

MONTHS = ["ENERO", "FEBRERO", "MARZO", "ABRIL", "MAYO", "JUNIO", "JULIO", "AGOSTO", "SEPTIEMBRE",
          "OCTUBRE", "NOVIEMBRE", "DICIEMBRE"]
WORD = re.compile(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)</word>')


def words(pdf: Path, page: int | None = None):
    args = ["pdftotext", "-bbox"] + (["-f", str(page), "-l", str(page)] if page else []) + [str(pdf), "-"]
    out = subprocess.run(args, capture_output=True, text=True, check=True).stdout
    return [(float(a), float(b), float(c), float(d), html.unescape(t)) for a, b, c, d, t in WORD.findall(out)]


def parse(pdf: Path) -> tuple[int | None, dict[int, float]]:
    W = words(pdf)
    text = " ".join(w[4] for w in W)
    m = re.search(r"Precio Productor\.?\s*-\s*(\d{4})", text) or re.search(r"Año:\s*(\d{4})", text)
    year = int(m.group(1)) if m else None
    # Eje de meses: la fila con más etiquetas ENERO…DICIEMBRE. El tablero de una página recorta algunas
    # (p. ej. SEPTIEMBRE, NOVIEMBRE, DICIEMBRE): se estiman por recta x = a + b·índice (meses equiespaciados).
    rows = {}
    for w in W:
        if w[4] in MONTHS:
            rows.setdefault(round(w[1]), []).append(w)
    if not rows:
        return year, {}
    y_axis, labels = max(rows.items(), key=lambda kv: len(kv[1]))
    pts = [(MONTHS.index(w[4]), (w[0] + w[2]) / 2) for w in labels]
    if len(pts) < 6:
        return year, {}
    n = len(pts)
    mx, my = sum(i for i, _ in pts) / n, sum(x for _, x in pts) / n
    b = sum((i - mx) * (x - my) for i, x in pts) / sum((i - mx) ** 2 for i, _ in pts)
    a = my - b * mx
    axis = {MONTHS[i]: a + b * i for i in range(12)}
    x0, x1 = axis["ENERO"] - b, axis["DICIEMBRE"] + b
    # techo del gráfico: el título "Precios …" más cercano por encima del eje
    tops = [w[1] for w in W if w[4] == "Precios" and w[1] < y_axis]
    top = max(tops) if tops else 0
    vals = []
    for i, w in enumerate(W):
        if re.fullmatch(r"\d{1,4}\.\d{2}", w[4]) and i > 0 and W[i - 1][4] == "$":
            xc = (W[i - 1][0] + w[2]) / 2
            if x0 <= xc <= x1 and top < w[1] < y_axis:
                vals.append((xc, float(w[4])))
    out = {}
    for xc, v in vals:
        mon = MONTHS.index(min(axis, key=lambda k: abs(axis[k] - xc))) + 1
        if mon in out:          # dos valores al mismo mes → asignación ambigua: descartar la ficha
            return year, {}
        out[mon] = v
    return year, out


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    rows, seen = [], {}
    for pdf in sorted(src.glob("*.pdf")):
        year, vals = parse(pdf)
        print(f"{pdf.name:28s} año={year} meses={len(vals)}", flush=True)
        if not year or len(vals) < 6:
            continue
        if year in seen:
            print(f"   (año {year} repetido con {seen[year]}; se conserva el primero)")
            continue
        seen[year] = pdf.name
        rows += [{"month": f"{year}-{m:02d}", "usd_per_qq": v, "source_file": pdf.name} for m, v in sorted(vals.items())]
    rows.sort(key=lambda r: r["month"])
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["month", "usd_per_qq", "source_file"])
        w.writeheader()
        w.writerows(rows)
    print(f"→ {dst} ({len(rows)} meses, años {sorted(seen)})")


if __name__ == "__main__":
    main()
