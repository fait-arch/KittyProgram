# ─────────────────────────────────────────────────────────────────────────────
# CacaoResiliente · despliegue en el servidor (sin Docker)
#
#   make            = make deploy
#   make deploy     instala deps (con toda la salida), compila FRONT-propuesta2 y levanta todo
#   make deploy-db  igual, y además carga las predicciones del modelo a Supabase
#   make update     git pull (conservando BACK/.env) + deploy
#   make restart    reinicia sin reinstalar dependencias
#   make stop       detiene todo
#   make status     ¿está vivo? (health del backend y del front)
#   make logs       sigue los logs
#
# Requisitos: python3 3.11+ con venv, Node 22+ (SvelteKit 3), npm, curl, y BACK/.env con las
# claves (NO se versiona: cp BACK/.env.example BACK/.env). Node 22 en Debian:
#   curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt install -y nodejs
# Puertos: API 8000 (solo localhost), front 8767 (público). Cambiar: make deploy P2_PORT=80
# ─────────────────────────────────────────────────────────────────────────────
SHELL := /bin/bash
.DEFAULT_GOAL := deploy
.PHONY: deploy deploy-db update restart stop status logs check install

BACK_PORT ?= 8000
P2_PORT   ?= 8767
LOG       := logs/produccion.log
PY        := BACK/venv/bin/python
# Sin NODE_ENV=production: vite está en devDependencies y npm ci no lo instalaría
RUN := env -u NODE_ENV BACK_PORT=$(BACK_PORT) P2_PORT=$(P2_PORT)

check:
	@echo "▶ Revisando requisitos"
	@for c in python3 node npm curl; do command -v $$c >/dev/null || { echo "✖ Falta $$c"; exit 1; }; done
	@echo "  python3 $$(python3 -V | cut -d' ' -f2) · node $$(node -v) · npm $$(npm -v)"
	@M=$$(node -p 'process.versions.node.split(".")[0]'); (( M >= 22 )) || { \
	  echo "✖ Node $$(node -v) es muy viejo: SvelteKit 3 necesita Node 22 o más."; \
	  echo "  Debian: curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && apt install -y nodejs"; exit 1; }
	@[[ -f BACK/.env ]] || { echo "✖ Falta BACK/.env  →  cp BACK/.env.example BACK/.env  y rellena las claves"; exit 1; }
	@grep -q '^DATA_SOURCE=supabase' BACK/.env || echo "⚠ BACK/.env no tiene DATA_SOURCE=supabase: la API servirá datos MOCK"
	@chmod +x produccion.sh

install: check
	@echo; echo "▶ Backend: entorno de Python (BACK/venv)"
	@[[ -x $(PY) ]] || python3 -m venv BACK/venv || { echo "✖ No se pudo crear el venv: apt install -y python3-venv"; exit 1; }
	@$(PY) -m pip -V >/dev/null 2>&1 || $(PY) -m ensurepip --upgrade
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r BACK/requirements.txt
	@echo; echo "▶ Frontend: dependencias npm (FRONT-propuesta2)"
	cd FRONT-propuesta2 && { env -u NODE_ENV npm ci --no-audit --no-fund || env -u NODE_ENV npm install --no-audit --no-fund; }

# Lanza produccion.sh en 2º plano (sobrevive al cerrar SSH), muestra su log en vivo y
# corta EN CUANTO el script muere, con su código de salida. Si algo falla, apaga lo que quedó.
define launch
	@./produccion.sh --detener >/dev/null 2>&1 || true
	@mkdir -p logs; : > $(LOG)
	@echo; echo "▶ produccion.sh $(1)   (log: $(LOG))"
	@$(RUN) nohup ./produccion.sh $(1) > $(LOG) 2>&1 & D=$$!; \
	tail -n +1 -f $(LOG) & T=$$!; trap "kill $$T 2>/dev/null" EXIT; ok=0; rc=""; \
	up() { curl -fs -o /dev/null http://127.0.0.1:$(BACK_PORT)/health && curl -fs -o /dev/null http://127.0.0.1:$(P2_PORT)/health; }; \
	for i in $$(seq 1 900); do \
	  if up; then ok=1; break; fi; \
	  if ! kill -0 $$D 2>/dev/null; then wait $$D; rc=$$?; sleep 2; up && ok=1; break; fi; \
	  sleep 1; done; \
	sleep 1; kill $$T 2>/dev/null; wait $$T 2>/dev/null; \
	echo; echo "──── logs/backend.log (últimas líneas) ────"; tail -n 20 logs/backend.log 2>/dev/null; \
	echo "──── logs/frontend-propuesta2.log (últimas líneas) ────"; tail -n 10 logs/frontend-propuesta2.log 2>/dev/null; \
	echo "──── /health ────"; curl -s http://127.0.0.1:$(BACK_PORT)/health; echo; echo; \
	if (( ok )); then \
	  curl -s http://127.0.0.1:$(BACK_PORT)/health | grep -q '"status":"ok"' || \
	    echo "⚠ Levantó, pero el backend está DEGRADADO: mira database.error y model.error en el /health de arriba"; \
	  echo "✔ CacaoResiliente arriba → http://<ip-del-servidor>:$(P2_PORT)   (API local :$(BACK_PORT); make logs para seguir)"; \
	else \
	  if [[ -n "$$rc" ]]; then echo "✖ produccion.sh MURIÓ con código $$rc antes de levantar todo: el error está arriba"; \
	  else echo "✖ No levantó en 15 min: revisa arriba y logs/"; fi; \
	  ./produccion.sh --detener >/dev/null 2>&1 || true; exit 1; \
	fi
endef

deploy: install
	$(call launch,--sin-instalar)

deploy-db: install
	$(call launch,--sin-instalar --cargar-db)

restart: check
	$(call launch,--sin-instalar)

# BACK/.env ya no se versiona: se respalda antes del pull y se restaura si git lo borra
update:
	@[[ -f BACK/.env ]] && cp -p BACK/.env BACK/.env.bak || true
	@git ls-files --error-unmatch BACK/.env >/dev/null 2>&1 && git checkout -- BACK/.env || true
	git pull --ff-only
	@[[ -f BACK/.env ]] || { [[ -f BACK/.env.bak ]] && cp -p BACK/.env.bak BACK/.env && echo "BACK/.env restaurado desde BACK/.env.bak"; }
	@[[ -f BACK/.env.bak ]] && ! cmp -s BACK/.env BACK/.env.bak && cp -p BACK/.env.bak BACK/.env && echo "BACK/.env restaurado desde BACK/.env.bak" || true
	@$(MAKE) --no-print-directory deploy

stop:
	@./produccion.sh --detener || true

status:
	@curl -fs http://127.0.0.1:$(BACK_PORT)/health && echo || echo "✖ backend caído"
	@curl -fs -o /dev/null http://127.0.0.1:$(P2_PORT)/ && echo "✔ front OK en :$(P2_PORT)" || echo "✖ front caído"

logs:
	tail -f logs/*.log
