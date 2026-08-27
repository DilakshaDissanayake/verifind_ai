# VERIFIND AI — Production-Level Execution Guide

**Audience:** operators / engineers bringing up a **production-like** or **demo-production** stack  
**Source of truth:** [`FINAL_PROJECT_PLAN.md`](./FINAL_PROJECT_PLAN.md)  
**Secrets walkthrough:** [`ENV_SETUP.md`](./ENV_SETUP.md)  
**Deploy skill contract:** `.cursor/skills/deploy-docker/SKILL.md`

> **Scope today:** Docker Compose `api` + `worker` + `redis` against managed Supabase (PostGIS + pgvector + storage).  
> **Later (Phase 2):** AWS ECS Fargate + ALB + secrets manager — not required for this guide.

---

## 0. What “production-level” means here

| Layer | Production expectation |
|---|---|
| API | FastAPI behind `0.0.0.0:8000`, real JWT, no reload, no auth bypass |
| Worker | Arq always on; `process_report_ai` → match → notify |
| Queue | Redis reachable; jobs not dropped silently |
| Data | Supabase pooler **6543**, schema + sprint migrations applied |
| Storage | `public-sanitized` (public) + `private-vault` (private) |
| Clients | Flutter + Admin SPA → HTTPS/API URL with real login |
| Safety | Vault / `hidden_features` never on public APIs; medium-risk → **REVIEW** (not auto-PASS) |

---

## 1. Prerequisites

| Tool | Why |
|---|---|
| [Docker Desktop](https://docs.docker.com/desktop/) | Compose stack (`api`, `worker`, `redis`) |
| [uv](https://docs.astral.sh/uv/) | Host scripts: schema, buckets, admin, smoke |
| Make + Git Bash (Windows) | Makefile recipes |
| Supabase project (Healthy) | Auth, DB, storage |
| OpenAI key (minimum) | Vision / embed / verify pipelines |
| Flutter 3.x (optional client) | Mobile against prod API |
| Node 20+ (optional client) | Admin REVIEW SPA |

```bash
# From repo root
docker --version
uv --version
make status
```

---

## 2. One-shot production bring-up (happy path)

```bash
# 1) Secrets
make env
# Edit .env → production values (see §3)

# 2) Host tooling (schema / smoke scripts)
make install

# 3) Data plane
make test-db
make init-schema
# Apply additive migrations if schema.sql is older than sprint SQL files:
#   sql/sprint4_5_migration.sql
#   sql/sprint6_migration.sql
#   sql/sprint7_migration.sql
# (Supabase SQL Editor, or psql against SUPABASE_DB_URL)
make ensure-buckets

# 4) Admin user (real Auth — bypass OFF)
make create-admin EMAIL=admin@yourdomain.com PASSWORD='strong-secret'

# 5) Stack
make up
make health

# 6) Clients (separate terminals)
make ui-install && make ui-dev
make mobile-get && make mobile-run   # or mobile-run-web / mobile-run-windows
```

**Expected health:** `GET http://localhost:8000/health` → `status: ok` (or `degraded` only if redis/db flagged offline — fix before demo).

---

## 3. Production `.env` contract

Template: [`.env.example`](../.env.example). Full secret sources: [`ENV_SETUP.md`](./ENV_SETUP.md).

### 3.1 Must change for production / demo-prod

```env
# --- Hardening ---
AUTH_DEV_BYPASS=false
API_RELOAD=false
LOG_LEVEL=INFO
ARQ_WORKER_ENABLED=true

# --- API ---
API_HOST=0.0.0.0
API_PORT=8000
# Real admin + any fixed web origins (Flutter web localhost regex still allowed by API)
CORS_ORIGINS=https://admin.yourdomain.com,http://localhost:5173

# --- Supabase (real project) ---
SUPABASE_URL=https://<ref>.supabase.co
SUPABASE_ANON_KEY=<anon>
SUPABASE_SERVICE_KEY=<service_role>          # SERVER ONLY
SUPABASE_JWT_SECRET=<jwt-secret>             # or rely on JWKS via SUPABASE_URL
SUPABASE_DB_URL=postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres

STORAGE_PUBLIC_BUCKET=public-sanitized
STORAGE_VAULT_BUCKET=private-vault

# --- Redis ---
# Host scripts / native make api|worker:
REDIS_URL=redis://localhost:6379/0
# Inside Compose, docker-compose.yml OVERRIDES to:
#   REDIS_URL=redis://redis:6379/0

# --- AI ---
OPENAI_API_KEY=sk-...
# Optional fallbacks: OPENROUTER_API_KEY, GROQ_API_KEY, ANTHROPIC_API_KEY, GOOGLE_API_KEY

# --- Observability (recommended for prod-like demos) ---
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### 3.2 Never do in production

| Anti-pattern | Why |
|---|---|
| `AUTH_DEV_BYPASS=true` | Fake tokens; anyone can act as admin/dev user |
| Ship `SUPABASE_SERVICE_KEY` to Flutter / React | Bypasses RLS; vault leak risk |
| Expose `private-vault` as public bucket | Zero-Fraud Layer 1 broken |
| Bake keys into Dockerfiles / images | Secrets in layers + registries |
| Auto-PASS medium fraud risk without admin REVIEW | Plan §5 / Shield Layer 4 |

### 3.3 Compose vs host Redis URL

| Where process runs | `REDIS_URL` |
|---|---|
| `make up` containers | Forced: `redis://redis:6379/0` |
| Host `make api` / `make worker` | `redis://localhost:6379/0` (Redis published on `6379`) |

---

## 4. Schema, migrations, storage

### 4.1 Base schema

```bash
make test-db          # PostGIS + pgvector must be present
make init-schema      # applies sql/schema.sql
```

### 4.2 Sprint migrations (additive)

If the project DB was created before later sprints, run in order in Supabase **SQL Editor**:

1. `sql/sprint4_5_migration.sql` — fraud / verify related deltas  
2. `sql/sprint6_migration.sql` — admin REVIEW support  
3. `sql/sprint7_migration.sql` — chat media / system messages  

All use `IF NOT EXISTS` / guarded constraints where possible — safe to re-run carefully.

### 4.3 Buckets

```bash
make ensure-buckets
```

| Bucket | Public | Contents |
|---|---|---|
| `public-sanitized` | Yes | Blurred images only |
| `private-vault` | **No** | Originals + `hidden_features` |

---

## 5. Run modes

### 5.A Production-like — Docker Compose (recommended)

```bash
make build          # images only
make up             # api + worker + redis (detached)
make logs           # API
make logs-worker    # Arq
make health
make down           # stop (volumes kept)
```

**Services** ([`docker-compose.yml`](../docker-compose.yml)):

| Service | Image / build | Role |
|---|---|---|
| `api` | `docker/Dockerfile.api` | uvicorn `api.main:app` :8000 |
| `worker` | `docker/Dockerfile.worker` | `arq workers.tasks.WorkerSettings` |
| `redis` | `redis:7-alpine` | Arq queue |

**Notes:**

- Compose mounts `./src` and `./config` for fast iteration; for a stricter prod image, rebuild without bind mounts and ship baked layers only.
- `restart: unless-stopped` keeps services up after Docker Desktop restarts.
- API Dockerfile installs `curl` for container health probes if you add them later.

### 5.B Hybrid — Compose Redis + native API/worker

Useful for debugging with hot reload **only on a private machine** (not public prod):

```bash
docker compose up -d redis
# .env: REDIS_URL=redis://localhost:6379/0, ARQ_WORKER_ENABLED=true, API_RELOAD=true (dev only)
make api      # terminal 1
make worker   # terminal 2
```

### 5.C Full native (no Docker)

Requires a reachable Redis (local install or remote). Prefer 5.A for demos.

---

## 6. Clients against the production API

### 6.1 React admin (REVIEW queue)

```bash
make ui-install
make ui-dev          # http://localhost:5173
```

- Login with the **real** Supabase admin user (`make create-admin`).
- Ensure that user has admin role in DB / Auth metadata as created by the script.
- Point the SPA at `http://localhost:8000` (or your public API URL) via its env / config — never embed `SUPABASE_SERVICE_KEY`.

### 6.2 Flutter mobile

```bash
make mobile-get
make mobile-run                    # Chrome → API_BASE_URL=http://localhost:8000
# or
make mobile-run-web                # http://127.0.0.1:8080
make mobile-run-windows
```

Override API:

```bash
make mobile-run API_URL=https://api.yourdomain.com
```

Product UX rules (locked):

- Device GPS + client fuzz ±500 m — **no** lat/lon text fields in product UI.
- Public feed shows sanitized images only.

---

## 7. Post-deploy verification checklist

### 7.1 Infrastructure

```bash
make status
make health
make test-db
```

| Check | Pass criteria |
|---|---|
| Health | `status` ok; `components.api` / `orchestrator` online |
| DB | PostGIS + vector extensions present |
| Redis | Worker logs show Arq connected; health redis not failing |
| Buckets | Upload path works; vault not listable anonymously |

### 7.2 Auth (bypass OFF)

- Register / login via Supabase email+password.
- `Authorization: Bearer <real-jwt>` on API calls.
- Dev token `Bearer dev` must **fail**.

### 7.3 Core product path (definition of done)

Aligned with plan §13:

1. **FOUND** report + photo → 202 Accepted → worker completes ≤ ~8 s AI budget.  
2. Public image blurred; vault private.  
3. **LOST** nearby → HIGH match (≥ 0.80) → notification.  
4. Claim → adversarial questions → PASS → chat; bad guess → FAIL / BLOCK / REVIEW.  
5. Admin opens REVIEW → vault vs public side-by-side (admin API only).

Quick Makefile smokes (use only while bypass is on **or** with real JWT tooling):

```bash
make report-smoke    # needs AUTH_DEV_BYPASS or real Bearer
make nearby-smoke
make demo-sprint6    # prints Sprint 6 demo asserts
```

With `AUTH_DEV_BYPASS=false`, prefer Flutter/admin UI or curl with a real access token instead of `Bearer dev`.

### 7.4 Automated tests (pre-release gate)

```bash
make test            # pytest -q
make test-sprint6    # fraud + admin
```

CI already runs pytest + admin typecheck on push (`.github/workflows/ci.yml`).

---

## 8. Day-2 operations

| Action | Command |
|---|---|
| Tail API | `make logs` |
| Tail worker | `make logs-worker` |
| Restart stack | `make restart` |
| Rebuild images | `make build && make up` |
| Wipe demo data (keep users) | `make wipe-data` |
| Stop | `make down` |

**After code changes:** rebuild/restart containers; run `graphify update .` for the knowledge graph (AST-only).

**Log files:** host `./logs` is mounted into the API container.

### 8.1 Incident quick map

| Symptom | Likely cause | Fix |
|---|---|---|
| Health fails | API down / port busy | `make logs`; free :8000; `make up` |
| Report 202 but no tags/match | Worker down / Redis URL | `make logs-worker`; check Compose `REDIS_URL` override |
| `503` / DB errors | Wrong pooler URL / password | Port **6543**; URL-encode password; `make test-db` |
| Login fails | Bypass off + bad keys | Verify anon + JWT; create user in Supabase Auth |
| Public image shows secrets | Sanitization failed | Check worker vision/sanitize logs; vault still private |
| Admin empty REVIEW | No medium-risk claims / role | Create claim path; confirm admin role |

---

## 9. Security & compliance gate (before any public URL)

- [ ] `AUTH_DEV_BYPASS=false`
- [ ] `API_RELOAD=false`
- [ ] `.env` not in git (`git status` clean of secrets)
- [ ] `SUPABASE_SERVICE_KEY` only in server / Compose secrets
- [ ] Vault bucket private; no public signed URLs on mobile feed APIs
- [ ] Public JSON never includes `hidden_features` or vault paths
- [ ] CORS limited to known admin / web origins
- [ ] Medium fraud risk stays **REVIEW** (admin) — not auto-PASS
- [ ] Rotate any key that appeared in chat, screenshots, or tickets
- [ ] Langfuse keys optional but do not log raw PII beyond policy

---

## 10. Runtime topology (this guide)

```
Flutter / Admin SPA
        │  HTTPS or http://localhost:8000
        ▼
   FastAPI (api)  ◄── .env (Supabase + OpenAI + …)
        │
        ├── LangGraph orchestrator + MCP tools
        ├── enqueue ──► Redis ──► Arq worker
        │                 process_report_ai
        │                 compute_matches → notify
        └── Supabase
              ├── Postgres (PostGIS + pgvector) via :6543
              ├── Auth (JWT)
              └── Storage: public-sanitized | private-vault
```

Config knobs (non-secret): `config/param.yaml`, `config/models.yaml`  
(fusion weights, geo radius 5 km, fraud thresholds, GPS fuzz 500 m, AI budget 8 s).

---

## 11. Out of scope (do not wait on these for this execution)

| Item | Status |
|---|---|
| ECS Fargate / ALB / OIDC deploy | Phase 2 |
| Qdrant primary vectors | Phase 2 optional |
| Voice / LiveKit / CRM / RAG | Explicitly out of MVP |
| Baking TLS termination in Compose | Use reverse proxy / cloud LB in front |

When ECS is ready: multi-stage images, no bind mounts, secrets from AWS SM/SSM, health check `GET /health`, separate task defs for `api` and `worker`, managed Redis (ElastiCache) or container Redis with persistence policy.

---

## 12. Command cheat sheet

```bash
make env && make install
make test-db && make init-schema && make ensure-buckets
make create-admin EMAIL=… PASSWORD=…
make up && make health
make logs | make logs-worker
make ui-dev
make mobile-run API_URL=http://localhost:8000
make test
make down
```

---

## Document map

| Doc | Role |
|---|---|
| [`FINAL_PROJECT_PLAN.md`](./FINAL_PROJECT_PLAN.md) | What to build |
| [`ENV_SETUP.md`](./ENV_SETUP.md) | How to obtain every secret |
| [`SPRINT1_TEST.md`](./SPRINT1_TEST.md) | Early local configure & smoke |
| [`TEST_PLAN.md`](./TEST_PLAN.md) | Formal test cases S1–S6 |
| **This file** | Production-level run / ops execution |
