# ─────────────────────────────────────────────────────────────────────────────
# CacaoResiliente · despliegue en el servidor (sin Docker)
#
#   make            = make deploy
#   make deploy     instala deps, compila FRONT-propuesta2 y levanta backend + front en 2º plano
#   make deploy-db  igual, y además carga las predicciones del modelo a Supabase
#   make update     git pull + deploy
#   make restart    reinicia sin reinstalar dependencias
#   make stop       detiene todo
#   make status     ¿está vivo? (health del backend y del front)
#   make logs       sigue los logs
#
# Usa ./produccion.sh por debajo. Requisitos: python3 3.11+ (con venv), node 20+, npm, curl
# y BACK/.env con las claves reales (DATA_SOURCE=supabase). Puertos: API 8000 (solo localhost),
# front 8767 (público). Cambiar con: make deploy P2_PORT=80 BACK_PORT=8000
# ─────────────────────────────────────────────────────────────────────────────
SHELL := /bin/bash
.DEFAULT_GOAL := deploy
.PHONY: deploy deploy-db update restart stop status logs check

BACK_PORT ?= 8000
P2_PORT   ?= 8767
LOG       := logs/produccion.log
# Sin NODE_ENV=production: vite está en devDependencies y npm ci no lo instalaría
RUN := env -u NODE_ENV BACK_PORT=$(BACK_PORT) P2_PORT=$(P2_PORT)

check:
	@[[ -f BACK/.env ]] || { echo "✖ Falta BACK/.env  →  cp BACK/.env.example BACK/.env  y rellena las claves"; exit 1; }
	@grep -q '^DATA_SOURCE=supabase' BACK/.env || echo "⚠ BACK/.env no tiene DATA_SOURCE=supabase: la API servirá datos MOCK"
	@chmod +x produccion.sh

define launch
	@./produccion.sh --detener >/dev/null 2>&1 || true
	@mkdir -p logs; : > $(LOG)
	@$(RUN) nohup ./produccion.sh $(1) > $(LOG) 2>&1 &
	@echo "Desplegando… (log: $(LOG); la 1ª vez tarda varios minutos)"
	@# Muestra el log en vivo mientras espera a que API y front respondan
	@tail -n +1 -f $(LOG) & T=$$!; trap "kill $$T 2>/dev/null" EXIT; ok=0; \
	for i in $$(seq 1 900); do \
	  if curl -fs -o /dev/null http://127.0.0.1:$(BACK_PORT)/health && \
	     curl -fs -o /dev/null http://127.0.0.1:$(P2_PORT)/health; then ok=1; break; fi; \
	  grep -q '✖' $(LOG) 2>/dev/null && break; \
	  sleep 1; done; \
	sleep 1; kill $$T 2>/dev/null; wait $$T 2>/dev/null; \
	echo; echo "──── logs/backend.log (últimas líneas) ────"; tail -n 15 logs/backend.log 2>/dev/null; \
	echo "──── logs/frontend-propuesta2.log (últimas líneas) ────"; tail -n 10 logs/frontend-propuesta2.log 2>/dev/null; \
	echo "──── /health ────"; curl -s http://127.0.0.1:$(BACK_PORT)/health; echo; echo; \
	if (( ok )) && ! curl -s http://127.0.0.1:$(BACK_PORT)/health | grep -q '"status":"ok"'; then \
	  echo "⚠ Levantó, pero el backend está DEGRADADO: mira database.error y model.error en el /health de arriba"; fi; \
	if (( ok )); then echo "✔ CacaoResiliente arriba → http://<ip-del-servidor>:$(P2_PORT)   (API local :$(BACK_PORT); make logs para seguir)"; \
	else echo "✖ El despliegue falló o no levantó a tiempo: revisa lo de arriba y logs/"; exit 1; fi
endef

deploy: check
	$(call launch,)

deploy-db: check
	$(call launch,--cargar-db)

restart: check
	$(call launch,--sin-instalar)

update:
	git pull --ff-only
	@$(MAKE) --no-print-directory deploy

stop:
	@./produccion.sh --detener || true

status:
	@curl -fs http://127.0.0.1:$(BACK_PORT)/health && echo || echo "✖ backend caído"
	@curl -fs -o /dev/null http://127.0.0.1:$(P2_PORT)/ && echo "✔ front OK en :$(P2_PORT)" || echo "✖ front caído"

logs:
	tail -f logs/*.log
