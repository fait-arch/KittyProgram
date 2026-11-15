#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# CacaoResiliente · levantar el sistema completo en modo producción (Linux)
#
#   ./produccion.sh                  instala, construye y levanta backend + frontend (propuesta 2)
#   ./produccion.sh --cargar-db      además carga a Supabase las predicciones del modelo (y 2050)
#   ./produccion.sh --front next     usa el frontend Next.js (FRONT/) en vez de la propuesta 2
#   ./produccion.sh --front ambos    levanta los dos frontends
#   ./produccion.sh --sin-instalar   no reinstala dependencias (arranque rápido)
#   ./produccion.sh --detener        detiene lo que dejó corriendo este script
#
# Requisitos: python3 (3.11+), node 20+ y npm, y BACK/.env con las claves (ver BACK/.env.example).
# Logs en logs/ · Ctrl+C detiene todo.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"
LOGS="$ROOT/logs"; mkdir -p "$LOGS"
PIDS="$LOGS/pids"

FRONT_MODE="propuesta2"; CARGAR_DB=0; INSTALAR=1
BACK_PORT="${BACK_PORT:-8000}"; P2_PORT="${P2_PORT:-8767}"; NEXT_PORT="${NEXT_PORT:-3000}"

verde() { printf '\033[1;32m%s\033[0m\n' "$*"; }
cafe()  { printf '\033[1;33m%s\033[0m\n' "$*"; }
error() { printf '\033[1;31m✖ %s\033[0m\n' "$*" >&2; exit 1; }
paso()  { printf '\n\033[1;36m▶ %s\033[0m\n' "$*"; }

detener() {
  if [[ -f "$PIDS" ]]; then
    while read -r pid; do kill "$pid" 2>/dev/null || true; done < "$PIDS"
    rm -f "$PIDS"
    verde "Servicios detenidos."
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --cargar-db) CARGAR_DB=1 ;;
    --front) FRONT_MODE="${2:-propuesta2}"; shift ;;
    --sin-instalar) INSTALAR=0 ;;
    --detener) detener; exit 0 ;;
    -h|--help) sed -n 2,15p "$0"; exit 0 ;;
    *) error "Opción desconocida: $1 (usa --help)" ;;
  esac
  shift
done
[[ "$FRONT_MODE" =~ ^(propuesta2|next|ambos)$ ]] || error "--front debe ser propuesta2, next o ambos"

# ── 1. Requisitos ────────────────────────────────────────────────────────────
paso "Revisando requisitos"
command -v python3 >/dev/null || error "Falta python3 (sudo apt install python3 python3-venv)"
command -v node >/dev/null    || error "Falta Node.js 20+ (https://nodejs.org o nvm)"
command -v npm >/dev/null     || error "Falta npm"
command -v curl >/dev/null    || error "Falta curl (sudo apt install curl)"
NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]')"
(( NODE_MAJOR >= 20 )) || error "Node $NODE_MAJOR es muy viejo: hace falta 20 o más"
[[ -f BACK/.env ]] || error "Falta BACK/.env (copia BACK/.env.example y pon las claves de Supabase y de la IA)"
echo "python3 $(python3 -V | cut -d' ' -f2) · node $(node -v) · npm $(npm -v)"

# El backend necesita estas variables para usar el modelo de ML de la raíz del repo
grep -q '^ML_INFERENCE_MODULE=' BACK/.env || echo 'ML_INFERENCE_MODULE=ml.inference' >> BACK/.env
grep -q '^PREDICTOR_MODE='     BACK/.env || echo 'PREDICTOR_MODE=local' >> BACK/.env
grep -q '^MODEL_PATH='         BACK/.env || echo 'MODEL_PATH=models/cacao_loss.joblib' >> BACK/.env

# ── 2. Backend (FastAPI) ────────────────────────────────────────────────────
paso "Backend: entorno de Python"
if [[ ! -x BACK/venv/bin/python ]] || ! BACK/venv/bin/python -c 'import sys' 2>/dev/null; then
  python3 -m venv BACK/venv || error "No se pudo crear el entorno (sudo apt install python3-venv)"
  INSTALAR=1
fi
PY="$ROOT/BACK/venv/bin/python"
if (( INSTALAR )); then
  "$PY" -m pip install -q --upgrade pip
  "$PY" -m pip install -q -r BACK/requirements.txt
  # Mismas versiones con que ML entrenó el modelo (si no, el .joblib no carga) + carga a la base
  "$PY" -m pip install -q "scikit-learn==1.9.1" pyarrow threadpoolctl python-dotenv statsmodels "psycopg[binary]"
fi
# Modelo entrenado → donde lo busca el backend
mkdir -p BACK/models
if [[ ml/artifacts/cacao_loss_v1.joblib -nt BACK/models/cacao_loss.joblib ]]; then
  cp ml/artifacts/cacao_loss_v1.joblib BACK/models/cacao_loss.joblib
  echo "Modelo copiado a BACK/models/cacao_loss.joblib"
fi

# ── 3. Base de datos (opcional) ─────────────────────────────────────────────
if (( CARGAR_DB )); then
  paso "Supabase: predicciones del modelo (país, provincias, cantones) y proyecciones 2050"
  "$PY" supabase/seed/tools/cargar_modelo.py
fi

# ── 4. Frontends ─────────────────────────────────────────────────────────────
if [[ "$FRONT_MODE" != "next" ]]; then
  paso "Frontend propuesta 2 (SvelteKit): compilando"
  pushd FRONT-propuesta2 >/dev/null
  if (( INSTALAR )) || [[ ! -d node_modules ]]; then npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund; fi
  npm run build
  popd >/dev/null
fi
if [[ "$FRONT_MODE" != "propuesta2" ]]; then
  paso "Frontend Next.js: compilando"
  pushd FRONT >/dev/null
  [[ -f .env.local ]] || printf 'BACKEND_URL=http://localhost:%s\nNEXT_PUBLIC_DATA_MODE=api\n' "$BACK_PORT" > .env.local
  if (( INSTALAR )) || [[ ! -d node_modules ]]; then npm ci --no-audit --no-fund 2>/dev/null || npm install --no-audit --no-fund; fi
  npm run build
  popd >/dev/null
fi

# ── 5. Levantar ──────────────────────────────────────────────────────────────
detener >/dev/null 2>&1 || true
puerto_libre() { ! (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null; }
for p in "$BACK_PORT" $([[ "$FRONT_MODE" != "next" ]] && echo "$P2_PORT") $([[ "$FRONT_MODE" != "propuesta2" ]] && echo "$NEXT_PORT"); do
  puerto_libre "$p" || error "El puerto $p está ocupado (¿quedó un 'npm run dev' o un uvicorn abierto?). Ciérralo o usa --detener."
done

paso "Levantando servicios"
: > "$PIDS"
trap 'echo; detener; exit 0' INT TERM

# Backend: solo en localhost; los frontends le reenvían /api (sin CORS ni exponer el puerto)
( cd BACK && exec "$PY" -m uvicorn run:app --host 127.0.0.1 --port "$BACK_PORT" --workers 2 --proxy-headers ) \
  > "$LOGS/backend.log" 2>&1 &
echo $! >> "$PIDS"

printf 'Esperando al backend'
for _ in $(seq 1 60); do
  if curl -fs "http://127.0.0.1:$BACK_PORT/health" >/dev/null 2>&1; then break; fi
  printf '.'; sleep 1
done
echo
curl -fs "http://127.0.0.1:$BACK_PORT/health" >/dev/null 2>&1 || { tail -30 "$LOGS/backend.log"; error "El backend no arrancó (ver logs/backend.log)"; }
SALUD="$(curl -s "http://127.0.0.1:$BACK_PORT/health")"
echo "$SALUD" | grep -q '"status":"ok"' && verde "Backend OK" || cafe "Backend con avisos: $SALUD"

if [[ "$FRONT_MODE" != "next" ]]; then
  ( cd FRONT-propuesta2 && BACKEND_URL="http://127.0.0.1:$BACK_PORT" exec npx vite preview --host 0.0.0.0 --port "$P2_PORT" --strictPort ) \
    > "$LOGS/frontend-propuesta2.log" 2>&1 &
  echo $! >> "$PIDS"
fi
if [[ "$FRONT_MODE" != "propuesta2" ]]; then
  ( cd FRONT && BACKEND_URL="http://127.0.0.1:$BACK_PORT" exec npx next start -H 0.0.0.0 -p "$NEXT_PORT" ) \
    > "$LOGS/frontend-next.log" 2>&1 &
  echo $! >> "$PIDS"
fi
sleep 4

IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
echo
verde "══════════════════════════════════════════════════════════════"
verde "  CacaoResiliente en producción"
[[ "$FRONT_MODE" != "next" ]]       && verde "  Propuesta 2:  http://localhost:$P2_PORT    ·  red local: http://$IP:$P2_PORT"
[[ "$FRONT_MODE" != "propuesta2" ]] && verde "  Next.js:      http://localhost:$NEXT_PORT    ·  red local: http://$IP:$NEXT_PORT"
verde "  API:          http://localhost:$BACK_PORT/docs   (solo en este equipo)"
verde "  Logs:         logs/   ·   Ctrl+C para detener todo"
verde "══════════════════════════════════════════════════════════════"

# Mantener vivo; si un servicio se cae, avisar y cerrar el resto
while true; do
  while read -r pid; do
    if ! kill -0 "$pid" 2>/dev/null; then
      cafe "Un servicio se detuvo (pid $pid). Revisa logs/. Cerrando el resto."
      detener; exit 1
    fi
  done < "$PIDS"
  sleep 5
done
