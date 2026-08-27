.PHONY: help install venv env status \
        init-schema test-db wipe-data ensure-buckets create-admin \
        api worker \
        up down restart logs logs-api logs-worker build \
        demo demo-down demo-logs \
        health report-smoke nearby-smoke \
        test test-all test-smoke test-sprint2 test-sprint6 \
        demo-sprint6 \
        ui-install ui-dev \
        mobile-get mobile-run mobile-run-web mobile-run-windows \
        graphify graphify-query \
        clean

# ---------------------------------------------------------------------------
# uv manages .venv (same pattern as Examples/aee-capstone)
#   make install  → uv sync   (creates .venv + installs deps)
#   make api/…    → uv run …  (uses .venv; no manual activate needed)
#
# Windows: MinGW make defaults to cmd.exe (breaks bash recipes). Force Git Bash.
# ---------------------------------------------------------------------------
ifeq ($(OS),Windows_NT)
  SHELL := C:/Progra~1/Git/bin/bash.exe
  .SHELLFLAGS := -c
endif

UV      ?= uv
PYTHON  := $(UV) run python
export PYTHONPATH := src
COMPOSE ?= docker compose
API_URL ?= http://localhost:8000
# Prefer FVM when mobile/.fvm/fvm_config.json exists (Flutter 3.38.5 pin).
MOBILE_FLUTTER := $(shell if [ -f mobile/.fvm/fvm_config.json ] && command -v fvm >/dev/null 2>&1; then echo "fvm flutter"; else echo "flutter"; fi)

.DEFAULT_GOAL := help

_check_uv:
	@$(UV) --version >/dev/null 2>&1 || ( \
		echo "❌ uv not found. Install: https://docs.astral.sh/uv/getting-started/installation/"; \
		echo "   Windows (PowerShell): irm https://astral.sh/uv/install.ps1 | iex"; \
		exit 1; \
	)

# ============================================================================
# HELP
# ============================================================================

help:
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║              VERIFIND AI — Makefile Commands                   ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "📦 SETUP (uv — auto .venv, no activate needed)"
	@echo "  make install              uv sync → create .venv + install deps"
	@echo "  make venv                 uv venv only (install does this too)"
	@echo "  make env                  Copy .env.example → .env (if missing)"
	@echo "  make status               Local stack / config status"
	@echo ""
	@echo "🗄️  DATABASE & STORAGE"
	@echo "  make init-schema          Apply sql/schema.sql (PostGIS + pgvector)"
	@echo "  make test-db              Ping DB + check postgis/vector"
	@echo "  make ensure-buckets       Create public-sanitized + private-vault"
	@echo "  make create-admin EMAIL=… PASSWORD=…  Supabase admin user + role"
	@echo ""
	@echo "🚀 NATIVE (no Docker) — uv run, auto uses .venv"
	@echo "  make api                  Run FastAPI (uvicorn reload)"
	@echo "  make worker               Run Arq worker (process_report_ai)"
	@echo ""
	@echo "🐳 DOCKER"
	@echo "  make up / demo            Build + start api + worker + redis"
	@echo "  make down / demo-down     Stop containers"
	@echo "  make restart              down + up"
	@echo "  make build                Build images only"
	@echo "  make logs / demo-logs     Tail api logs"
	@echo "  make logs-worker          Tail worker logs"
	@echo ""
	@echo "🩺 SMOKE"
	@echo "  make health               GET /health"
	@echo "  make report-smoke         POST /reports → 202 + DB persist"
	@echo "  make nearby-smoke         GET /reports/nearby (PostGIS)"
	@echo ""
	@echo "🧪 TESTS"
	@echo "  make test / test-all      pytest -q"
	@echo "  make test-smoke           Sprint 1 smoke only"
	@echo "  make test-sprint2         Sprint 2 reports/geo tests"
	@echo "  make test-sprint6         Sprint 5–6 fraud + admin tests"
	@echo "  make demo-sprint6         Print §13 demo path + core asserts"
	@echo ""
	@echo "📱 CLIENTS"
	@echo "  make ui-install           npm install in ui/ (admin REVIEW)"
	@echo "  make ui-dev               npm run dev → http://localhost:5173"
	@echo "  make mobile-get           flutter pub get"
	@echo "  make mobile-run           Flutter Chrome (IPv4 + local CanvasKit)"
	@echo "  make mobile-run-web       Flutter web-server → http://127.0.0.1:8080"
	@echo "  make mobile-run-windows   Flutter Windows desktop (no Chrome DWDS)"
	@echo ""
	@echo "🕸  GRAPHIFY"
	@echo "  make graphify             graphify update ."
	@echo "  make graphify-query Q=…   graphify query \"\$$Q\""
	@echo ""
	@echo "🧹 CLEAN"
	@echo "  make wipe-data            Delete all reports/matches/chats (keep users)"
	@echo "  make clean                Remove caches / pyc / pytest junk"
	@echo ""
	@echo "💡 Quick start:"
	@echo "   make env && make install && make up && make health"
	@echo ""

# ============================================================================
# SETUP
# ============================================================================

venv: _check_uv
	@echo "📦 Creating .venv with uv …"
	$(UV) venv
	@echo "✅ .venv ready. Prefer: make install (syncs deps too)"
	@echo "   Optional activate (PowerShell): .\\.venv\\Scripts\\Activate.ps1"
	@echo "   Optional activate (bash/Git Bash): source .venv/bin/activate"
	@echo "   make api / make test already use uv run — activate not required"

install: _check_uv
	@echo "📦 uv sync (creates .venv if missing + installs from pyproject.toml)…"
	$(UV) sync
	@echo "✅ Installation complete — .venv ready"
	@echo "   No need to activate; make api / make test use: uv run"

env:
	@if [ -f .env ]; then \
		echo "✅ .env already exists"; \
	else \
		cp .env.example .env; \
		echo "✅ Copied .env.example → .env — fill secrets before make up"; \
	fi

status: _check_uv
	@echo "╔════════════════════════════════════════════════════════════════╗"
	@echo "║                    VERIFIND System Status                      ║"
	@echo "╚════════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "🔧 Runtime"
	@echo "  uv: $$($(UV) --version 2>&1)"
	@echo "  Python: $$($(PYTHON) --version 2>&1)"
	@echo "  PYTHONPATH: $(PYTHONPATH)"
	@if [ -d .venv ]; then echo "  .venv: present (uv-managed)"; else echo "  .venv: MISSING (make install)"; fi
	@if [ -f .env ]; then echo "  .env: present"; else echo "  .env: MISSING (make env)"; fi
	@if [ -f config/param.yaml ]; then echo "  config/param.yaml: ok"; else echo "  config/param.yaml: missing"; fi
	@if [ -f config/models.yaml ]; then echo "  config/models.yaml: ok"; else echo "  config/models.yaml: missing"; fi
	@if [ -f sql/schema.sql ]; then echo "  sql/schema.sql: ok"; else echo "  sql/schema.sql: missing"; fi
	@echo ""
	@echo "🐳 Docker (compose)"
	@$(COMPOSE) ps 2>/dev/null || echo "  (compose not running or docker unavailable)"
	@echo ""
	@echo "📂 Clients"
	@if [ -f ui/package.json ]; then echo "  ui/: admin REVIEW SPA present"; else echo "  ui/: missing"; fi
	@if [ -f mobile/pubspec.yaml ]; then echo "  mobile/: Flutter present"; else echo "  mobile/: missing"; fi
	@echo ""
	@echo "💡 Next: make up && make health && make ui-dev"

# ============================================================================
# DATABASE & STORAGE
# ============================================================================

init-schema: _check_uv
	@echo "🚀 Applying sql/schema.sql …"
	@$(PYTHON) scripts/init_schema.py

wipe-data: _check_uv
	@echo "🧹 Wiping reports / matches / claims / chats / notifications …"
	@$(PYTHON) scripts/wipe_app_data.py --yes

test-db: _check_uv
	@echo "🔍 Testing DB + extensions…"
	@$(PYTHON) scripts/test_db.py

ensure-buckets: _check_uv
	@echo "🪣 Ensuring storage buckets…"
	@$(PYTHON) scripts/ensure_buckets.py

create-admin: _check_uv
	@if [ -z "$(EMAIL)" ] || [ -z "$(PASSWORD)" ]; then \
		echo "Usage: make create-admin EMAIL=admin@gmail.com PASSWORD='your-secret'"; \
		exit 1; \
	fi
	@$(PYTHON) scripts/create_admin_user.py --email "$(EMAIL)" --password "$(PASSWORD)"

# ============================================================================
# NATIVE RUN
# ============================================================================

api: _check_uv
	@echo "🚀 FastAPI → http://localhost:8000/docs"
	@$(PYTHON) -m api.run

worker: _check_uv
	@echo "⚙️  Arq worker (workers.tasks.WorkerSettings)"
	@ARQ_WORKER_ENABLED=true $(PYTHON) -m arq workers.tasks.WorkerSettings

# ============================================================================
# DOCKER
# ============================================================================

_check_env:
	@if [ ! -f .env ]; then \
		echo "❌ No .env found."; \
		echo "   Run: make env   then fill SUPABASE_* / OPENAI_* / REDIS_URL"; \
		exit 1; \
	fi

up demo: _check_env
	@echo "🐳 Building + starting api + worker + redis…"
	$(COMPOSE) up --build -d
	@echo ""
	@echo "✅ Stack up"
	@echo "   API    → $(API_URL)  (docs: /docs)"
	@echo "   Health → make health"
	@echo "   Logs   → make logs | make logs-worker"
	@echo "   Stop   → make down"

down demo-down:
	$(COMPOSE) down
	@echo "✅ Stack stopped (add -v manually to wipe volumes)"

restart: down up

build: _check_env
	$(COMPOSE) build

logs demo-logs:
	$(COMPOSE) logs -f api

logs-api: logs

logs-worker:
	$(COMPOSE) logs -f worker

# ============================================================================
# SMOKE
# ============================================================================

health: _check_uv
	@echo "🩺 GET $(API_URL)/health"
	@curl -sf "$(API_URL)/health" | $(PYTHON) -m json.tool || \
		(echo "❌ Health failed — is the API up? (make up / make api)"; exit 1)

report-smoke: _check_uv
	@echo "📨 POST $(API_URL)/api/v1/reports (dev bypass auth — persists + fuzzes GPS)"
	@curl -sf -X POST "$(API_URL)/api/v1/reports" \
		-H "Content-Type: application/json" \
		-H "Authorization: Bearer dev" \
		-d '{"report_type":"LOST","title":"smoke test","description":"makefile smoke","latitude":6.9271,"longitude":79.8612,"location_label":"Colombo"}' \
		| $(PYTHON) -m json.tool || \
		(echo "❌ report-smoke failed"; exit 1)

nearby-smoke: _check_uv
	@echo "📍 GET $(API_URL)/api/v1/reports/nearby"
	@curl -sf "$(API_URL)/api/v1/reports/nearby?lat=6.9271&lon=79.8612&radius_m=5000" \
		-H "Authorization: Bearer dev" \
		| $(PYTHON) -m json.tool || \
		(echo "❌ nearby-smoke failed — create a report first (make report-smoke)"; exit 1)

# ============================================================================
# TESTS
# ============================================================================

test test-all: _check_uv
	@echo "🧪 pytest -q"
	@$(PYTHON) -m pytest tests/ -q --tb=line

test-smoke: _check_uv
	@echo "🧪 Sprint 1 smoke"
	@$(PYTHON) -m pytest tests/test_sprint1_smoke.py -q --tb=line

test-sprint2: _check_uv
	@echo "🧪 Sprint 2 reports + geo"
	@$(PYTHON) -m pytest tests/test_sprint2_reports_geo.py -q --tb=line

test-sprint6: _check_uv
	@echo "🧪 Sprint 5–6 fraud + admin REVIEW"
	@$(PYTHON) -m pytest tests/test_sprint5_6_admin_harden.py -q --tb=line

demo-sprint6: _check_uv
	@echo "🎬 Sprint 6 demo checklist"
	@$(PYTHON) scripts/demo_sprint6.py

# ============================================================================
# CLIENTS
# ============================================================================

ui-install:
	@if [ ! -f ui/package.json ]; then \
		echo "❌ ui/package.json missing"; \
		exit 1; \
	fi
	cd ui && npm install

ui-dev:
	@if [ ! -f ui/package.json ]; then \
		echo "❌ ui/package.json missing"; \
		exit 1; \
	fi
	cd ui && npm run dev

mobile-get:
	@if [ ! -f mobile/pubspec.yaml ]; then \
		echo "❌ mobile/pubspec.yaml missing"; \
		exit 1; \
	fi
	cd mobile && $(MOBILE_FLUTTER) pub get

# Chrome 151 + Flutter 3.47 DWDS: Debugger.enable often times out on Windows
# when localhost is IPv6 or CanvasKit is fetched from gstatic. Bind 127.0.0.1
# and serve engine assets locally. If attach still fails: make mobile-run-web
mobile-run:
	@if [ ! -f mobile/pubspec.yaml ]; then \
		echo "❌ mobile/pubspec.yaml missing"; \
		exit 1; \
	fi
	cd mobile && $(MOBILE_FLUTTER) run -d chrome \
		--web-hostname 127.0.0.1 \
		--no-web-resources-cdn \
		--dart-define=API_BASE_URL=$(API_URL)

mobile-run-web:
	@if [ ! -f mobile/pubspec.yaml ]; then \
		echo "❌ mobile/pubspec.yaml missing"; \
		exit 1; \
	fi
	@echo "🌐 Web-server (no Chrome debug attach). Open http://127.0.0.1:8080"
	cd mobile && $(MOBILE_FLUTTER) run -d web-server \
		--web-hostname 127.0.0.1 \
		--web-port 8080 \
		--dart-define=API_BASE_URL=$(API_URL)

mobile-run-windows:
	@if [ ! -f mobile/pubspec.yaml ]; then \
		echo "❌ mobile/pubspec.yaml missing"; \
		exit 1; \
	fi
	cd mobile && $(MOBILE_FLUTTER) run -d windows --dart-define=API_BASE_URL=$(API_URL)

# ============================================================================
# GRAPHIFY
# ============================================================================

graphify:
	@echo "🕸  graphify update ."
	graphify update .

graphify-query:
	@if [ -z "$(Q)" ]; then \
		echo "Usage: make graphify-query Q=\"your question\""; \
		exit 1; \
	fi
	graphify query "$(Q)"

# ============================================================================
# CLEAN
# ============================================================================

clean:
	@echo "🧹 Cleaning caches…"
	@rm -rf .pytest_cache .mypy_cache .ruff_cache htmlcov .coverage 2>/dev/null || true
	@find . -type d -name __pycache__ -not -path "./Examples/*" -not -path "./.venv/*" -prune -exec rm -rf {} + 2>/dev/null || true
	@find . -type f -name "*.pyc" -not -path "./Examples/*" -not -path "./.venv/*" -delete 2>/dev/null || true
	@echo "✅ Cleaned (Examples/, .venv, cloud data untouched)"
