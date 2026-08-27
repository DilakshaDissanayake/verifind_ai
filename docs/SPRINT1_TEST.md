# Sprint 1–2 — Full Configure & Test Guide

**Status:** Sprint 1 foundation **and** Sprint 2 (Reports + Geo) are implemented. Use this doc end-to-end to prove both.  
**Full test register (all sprints + evidence columns):** [`TEST_PLAN.md`](./TEST_PLAN.md)

**Plan exit criteria** ([`FINAL_PROJECT_PLAN.md`](./FINAL_PROJECT_PLAN.md) §9):

### Sprint 1

| Criterion | How you prove it |
|---|---|
| Scaffold wired (FastAPI, config, Auth, schema, Flutter shell, LLM wrapper) | Steps 1–4 + 10 |
| `/health` green (API online) | Step 6 |
| Login works | Step 7 |
| `POST /reports` → **202** | Step 8 |
| Worker consumes the job | Step 9 |
| Automated smoke green | Step 11 |

### Sprint 2

| Criterion | How you prove it |
|---|---|
| Create LOST/FOUND **persisted** in `reports` | Step 8 + Step 15 (DB row) |
| Image upload → `report_images` + vault | Step 16 |
| GPS fuzz ±500 m (client + server) | Step 8 response lat/lon ≠ raw input; Flutter Step 10 |
| PostGIS `ST_DWithin` nearby ≤5 km | Step 17 (`make nearby-smoke`) |
| EXIF extract (GPS stripped on public API) | Step 16 response `exif` has no `GPSInfo` |
| Automated S2 tests green | Step 18 |

**What Sprint 1 ships (in scope)**

- `uv` + `Makefile` setup (`.venv` via `uv sync`)
- FastAPI: `/health`, `/api/v1/auth/login`, `/api/v1/auth/me`, `/api/v1/reports`
- Supabase Auth (or `AUTH_DEV_BYPASS` for local smoke)
- `sql/schema.sql` (PostGIS + pgvector + MVP tables)
- Storage buckets: `public-sanitized`, `private-vault`
- Arq worker: `process_report_ai` (S2 marks `processing`; full AI is S3)
- LangGraph orchestrator + MCP server shells
- `config/param.yaml`, `config/models.yaml`, OpenAI wrapper soft-attach
- Flutter shell: Login + **Register** + Create Report
- Docker Compose: `api` + `worker` + `redis`

**What Sprint 2 adds**

- Report **CRUD**: create (persist), get, list mine, patch
- Server GPS fuzz (`gps.fuzz_meters: 500`) + Flutter **device GPS** (no manual lat/lon product fields) + client fuzz
- `GET /api/v1/reports/nearby` — PostGIS `ST_DWithin` (default 5 km); Flutter Nearby uses phone location
- `POST /api/v1/reports/{id}/images` — multipart upload → `private-vault` + `exif_json`
- `pipelines/metadata_pipeline.py` — EXIF extract; public responses strip GPS/serials
- Services: `report_service`, `geo_service`, `image_service`, `user_service`
- MCP helpers on `geo_server` / `report_server` (tool functions; stdio wiring later)

**Out of scope (do not fail Sprint 1–2 for these)**

- Vision / text embed / fusion (S3)
- Public blur / vault `hidden_features` on admin UI (S4)
- Claim verify / chat / admin REVIEW (S5–S6)

---

## 0. Prerequisites (do once)

Tick each box before continuing.

- [ ] **Git** — repo cloned; you are in repo root `verifind-ai/`
- [ ] **Python 3.11+** — `python --version` (or `py -3.11 --version` on Windows)
- [ ] **uv** — `uv --version`  
  - Missing? PowerShell: `irm https://astral.sh/uv/install.ps1 | iex`  
  - Docs: https://docs.astral.sh/uv/getting-started/installation/
- [ ] **GNU Make** — `make help` prints VERIFIND commands  
  - Windows: use **Git Bash** (or WSL), not plain `cmd`
- [ ] **Docker Desktop** — running (needed for `make up` / Redis)  
  - https://docs.docker.com/desktop/
- [ ] **Supabase project** — Auth + Postgres (Dashboard: https://supabase.com/dashboard)
- [ ] **Flutter SDK** (optional Step 10) — `flutter --version`  
  - https://docs.flutter.dev/get-started/install

---

## 1. Create `.env`

```bash
cd /path/to/verifind-ai
make env
```

**Pass if:** message says `.env` created (or already exists).

Open `.env` and replace every `replace-me` / `your-project` / `sk-replace-me` placeholder.

| Variable | Required for S1? | Notes |
|---|---|---|
| `SUPABASE_URL` | Yes (for real Auth + buckets) | Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Yes (real login) | `anon` `public` |
| `SUPABASE_SERVICE_KEY` | Yes (buckets / server) | `service_role` — never ship to Flutter |
| `SUPABASE_JWT_SECRET` | Yes (real JWT `/me`) | Settings → API → JWT Secret |
| `SUPABASE_DB_URL` | Yes (schema / `test-db` / health db) | **Transaction pooler port `6543`**, not `5432` |
| `STORAGE_PUBLIC_BUCKET` | Yes | default `public-sanitized` |
| `STORAGE_VAULT_BUCKET` | Yes | default `private-vault` |
| `REDIS_URL` | Yes (worker path) | Native: `redis://localhost:6379/0` · Docker: see Step 5 |
| `AUTH_DEV_BYPASS` | Yes for first smoke | `true` until real Auth tested |
| `AUTH_DEV_USER_ID` / `AUTH_DEV_EMAIL` | With bypass | defaults OK |
| `ARQ_WORKER_ENABLED` | For enqueue | `true` when testing worker; Docker worker sets this itself |
| `OPENAI_API_KEY` | Soft (S1) | Not required for health/login/report stub |
| `OPENROUTER_*` / `GROQ_*` / … / `LANGFUSE_*` | Optional | Later sprints |

**Full secret walkthrough (every click):** [`ENV_SETUP.md`](./ENV_SETUP.md)  
**Template:** [`.env.example`](../.env.example)

Then:

```bash
make status
```

**Pass if:** `.env: present`, `config/param.yaml: ok`, `config/models.yaml: ok`, `sql/schema.sql: ok`.  
**Fail if:** `.env: MISSING` → re-run `make env`.

---

## 2. Install Python deps (`uv` → auto `.venv`)

```bash
make install
```

What this does: `uv sync` → creates `.venv` if missing + installs from `pyproject.toml` / `uv.lock`.

**Pass if:** ends with `Installation complete — .venv ready`.  
**Fail if:** `uv not found` → install uv (Step 0), reopen terminal, retry.

You do **not** need to activate the venv. All `make api` / `make test` / scripts use `uv run`.

Optional check:

```bash
uv run python --version
```

---

## 3. Apply DB schema

Requires a valid `SUPABASE_DB_URL` (pooler `:6543`).

```bash
make init-schema
```

**Pass if:** log shows `Schema applied.`  
**Fail if:** connection error → fix password / project-ref / region / **port 6543** in `.env` ([ENV_SETUP.md](./ENV_SETUP.md) § database).

What gets created (idempotent `IF NOT EXISTS`): extensions `postgis`, `vector`, `pgcrypto` + MVP tables (`users`, `reports`, `report_images`, `ai_tags`, `image_vaults`, `matches`, …).

---

## 4. Verify DB + storage buckets

### 4a. Database ping + extensions

```bash
make test-db
```

**Pass if:**

- `Connection OK`
- `postgis=True  pgvector=True`
- `All DB checks passed.`

**Fail if:** missing extensions → re-run `make init-schema` (and ensure PostGIS is available on the Supabase project).

### 4b. Storage buckets

```bash
make ensure-buckets
```

**Pass if:** `Buckets OK` (created or already present).  
**Fail if:** bad `SUPABASE_URL` / `SUPABASE_SERVICE_KEY` → fix API keys, retry.  
Manual fallback: Dashboard → Storage → create `public-sanitized` + `private-vault`  
https://supabase.com/dashboard/project/_/storage/buckets

---

## 5. Start the stack

Pick **one** path. Docker is the default Sprint 1 path.

### Path A — Docker (recommended)

**Before `make up`, set Redis for containers** in `.env`:

```env
REDIS_URL=redis://redis:6379/0
ARQ_WORKER_ENABLED=true
AUTH_DEV_BYPASS=true
```

> Inside Compose, the Redis hostname is `redis`, not `localhost`.  
> If you later run native `make api` on the host, switch back to `redis://localhost:6379/0`.

```bash
make up
```

**Pass if:** containers start; printed URLs include API `http://localhost:8000`.

Watch logs (separate terminals optional):

```bash
make logs           # API
make logs-worker    # Arq worker
```

**Pass if:** API log shows startup (`Starting VERIFIND AI API`); worker shows `Arq worker started (Sprint 1)`.

Stop later:

```bash
make down
```

### Path B — Native (no Docker API)

1. Start Redis only (example):

```bash
docker compose up -d redis
```

2. In `.env`:

```env
REDIS_URL=redis://localhost:6379/0
ARQ_WORKER_ENABLED=true
AUTH_DEV_BYPASS=true
```

3. Two terminals:

```bash
make api       # terminal 1 → http://localhost:8000/docs
make worker    # terminal 2 → Arq
```

**Pass if:** both processes stay up without import errors.

---

## 6. Live smoke — `/health`

```bash
make health
```

Or:

```bash
curl -s http://localhost:8000/health
```

**Expect (shape):**

```json
{
  "status": "ok",
  "service": "VERIFIND AI",
  "version": "0.1.0-sprint1",
  "uptime_seconds": 12.34,
  "components": {
    "api": "online",
    "orchestrator": "online",
    "redis": "online",
    "db": "online"
  }
}
```

| Field | Sprint 1 pass rule |
|---|---|
| HTTP | `200` |
| `components.api` | must be `"online"` |
| `components.orchestrator` | must be `"online"` |
| `status` | `"ok"` when api+orchestrator online (even if db/redis probe failed → still often `"ok"` from current code) |
| `components.db` | `"online"` if `SUPABASE_DB_URL` good; else `"offline"` / `"skipped"` |
| `components.redis` | `"online"` if Redis reachable; else `"offline"` |

**Also open:** http://localhost:8000/docs — Swagger should list health, auth, reports.

**Fail if:** connection refused → stack not up (`make up` / `make api`).

---

## 7. Live smoke — login + `/me`

### 7a. Dev bypass (first smoke)

`.env` must have `AUTH_DEV_BYPASS=true` and placeholder Supabase URL/keys (or bypass path will try real Supabase).

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"dev@example.com\",\"password\":\"password\"}"
```

**Pass if:** HTTP `200` and body like:

```json
{
  "access_token": "dev-bypass-token",
  "token_type": "bearer",
  "user_id": "00000000-0000-0000-0000-000000000001",
  "email": "dev@example.com",
  "role": "user",
  "mode": "dev_bypass"
}
```

### 7b. `/me` with bypass

With `AUTH_DEV_BYPASS=true`, bearer can be anything (deps ignore token and return dev user):

```bash
curl -s http://localhost:8000/api/v1/auth/me \
  -H "Authorization: Bearer dev"
```

**Pass if:** `200`, `user_id` matches `AUTH_DEV_USER_ID`, email matches `AUTH_DEV_EMAIL`.

### 7c. Real Supabase Auth (after keys filled)

1. Create a user in Supabase Auth (Dashboard → Authentication → Users → Add user), or sign up via your client.
2. Set in `.env`:

```env
AUTH_DEV_BYPASS=false
```

3. Restart stack (`make down && make up` or restart native processes).
4. Login with that email/password:

```bash
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"YOUR_USER@example.com\",\"password\":\"YOUR_PASSWORD\"}"
```

**Pass if:** `200`, `mode: "supabase"`, non-empty `access_token`.  
Then call `/me` with that token — **Pass if:** `200` and matching `user_id`.

**Fail if:** `401` → wrong password, wrong anon key, or JWT secret mismatch.

---

## 8. Live smoke — create report → 202

```bash
make report-smoke
```

Or:

```bash
curl -s -X POST http://localhost:8000/api/v1/reports \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev" \
  -d "{\"report_type\":\"LOST\",\"title\":\"smoke test\",\"description\":\"makefile smoke\",\"latitude\":6.9271,\"longitude\":79.8612}"
```

**Pass if:** HTTP **202** and body like:

```json
{
  "report_id": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "status": "pending",
  "message": "Accepted for AI processing",
  "job_enqueued": true,
  "latitude": 6.92xx,
  "longitude": 79.86xx
}
```

| Field | Rule |
|---|---|
| `status` | `"pending"` |
| `report_id` | present UUID |
| `job_enqueued` | `true` when `ARQ_WORKER_ENABLED=true` **and** Redis reachable; else `false` (API still returns 202) |
| `latitude` / `longitude` | **Sprint 2:** present when you sent coords; values are **server-fuzzed** (±500 m) — usually ≠ exact input |

**Sprint 2:** a row **must** appear in Supabase `reports` (see Step 15).  
**Fail if:** `401` with bypass off and bad token · `422` on bad payload · `503` DB down · connection error.

---

## 9. Worker consumed the job

With Redis + worker running and `ARQ_WORKER_ENABLED=true` on the **API** (so enqueue happens):

1. Run Step 8 again.
2. Check worker logs:

```bash
make logs-worker
# native: watch the `make worker` terminal
```

**Pass if:** a line like:

```text
process_report_ai stub report_id=<same-uuid> status=processing
```

(or `process_report_ai stub report_id=…` if DB update was skipped)

Also acceptable on API logs when Arq disabled:

```text
ARQ disabled — stub process_report_ai …
```

That proves the intake path; enable Arq for the full exit criterion (worker log).

---

## 10. Flutter shell (S1 + S2 GPS fuzz)

```bash
make mobile-get
```

Run against the API (emulator / device):

```bash
# Android emulator → host machine API
cd mobile
flutter run --dart-define=API_BASE_URL=http://10.0.2.2:8000

# iOS simulator / desktop / same machine
flutter run --dart-define=API_BASE_URL=http://localhost:8000
```

Manual UI checklist:

- [ ] Login screen opens
- [ ] **Create account** screen works (email + password + optional name)
- [ ] With `AUTH_DEV_BYPASS=true`, login/register succeed for smoke
- [ ] With real Supabase (`AUTH_DEV_BYPASS=false`), new users can sign up
- [ ] Create Report: **phone GPS auto** (no lat/lon typing) + ±500 m fuzz + optional photo
- [ ] Nearby screen uses phone GPS and lists ≤5 km reports
- [ ] UI shows success / pending (202) — no crash

**Pass if:** auth + create report work against live API.  
**Fail if:** wrong `API_BASE_URL` (phone cannot reach `localhost` — use LAN IP).

---

## 11. Automated tests (no live server required)

Uses FastAPI `TestClient` + forced `AUTH_DEV_BYPASS=true` (DB mocked where needed).

```bash
make test-smoke
make test-sprint2
# or full:
make test
```

**Pass if:** all green — covers:

| Test file | Asserts |
|---|---|
| `test_sprint1_smoke.py` | `/health` · login · POST `/reports` → 202 |
| `test_sprint2_reports_geo.py` | GPS fuzz bound · EXIF strip · nearby mock · CRUD mock · upload no vault leak |

**Fail if:** import errors / assertion failures → fix code or env cache; re-run.

---

## 12. Pass / fail summary — Sprint 1 (sign-off)

Tick when done. Sprint 1 is **configured & tested** only if all required rows pass.

| # | Check | Required? | Pass means |
|---|---|---|---|
| 1 | `make env` + filled `.env` | Yes | No placeholders left for P0 keys you will use |
| 2 | `make install` | Yes | `.venv` + deps via uv |
| 3 | `make status` | Yes | env + yaml + schema files present |
| 4 | `make init-schema` | Yes* | Schema applied (*skip only if already applied) |
| 5 | `make test-db` | Yes | Ping OK; postgis + vector |
| 6 | `make ensure-buckets` | Yes | Buckets OK |
| 7 | `make up` (or native api+worker) | Yes | Stack running |
| 8 | `make health` | Yes | HTTP 200; `api` + `orchestrator` online |
| 9 | Login curl | Yes | `dev_bypass` or `supabase` + token |
| 10 | `/me` | Recommended | 200 with user |
| 11 | `make report-smoke` | Yes | **202** + `pending` + `report_id` |
| 12 | Worker log | Yes | `process_report_ai … report_id=…` |
| 13 | `make test-smoke` | Yes | Pytest green |
| 14 | Flutter shell | Recommended | Login + create report against API |

**Signed off when:** 8 + 9 + 11 + 12 + 13 all pass.

---

## 15. Sprint 2 — Prove report row persisted

After Step 8 (`make report-smoke`), open Supabase **Table Editor → `reports`** (or SQL):

```sql
SELECT id, report_type, status, title,
       ST_Y(location::geometry) AS lat,
       ST_X(location::geometry) AS lon,
       created_at
FROM reports
ORDER BY created_at DESC
LIMIT 5;
```

**Pass if:** newest row matches smoke `report_id`; `location` is set; lat/lon ≈ Colombo but **not** exactly `6.9271, 79.8612` (server fuzz).  
Also create a FOUND report and confirm both types insert.

```bash
curl -s -X POST http://localhost:8000/api/v1/reports \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev" \
  -d "{\"report_type\":\"FOUND\",\"title\":\"found bag\",\"latitude\":6.9280,\"longitude\":79.8620}"
```

**Fail if:** `503 Database unavailable` → fix `SUPABASE_DB_URL` / re-run `make init-schema`.

---

## 16. Sprint 2 — Image upload + EXIF

```bash
# create a tiny JPEG then upload (Git Bash)
python - <<'PY'
from pathlib import Path
try:
    from PIL import Image
except ImportError:
    raise SystemExit("pip/uv: install Pillow first (make install)")
p = Path("tmp_smoke.jpg")
Image.new("RGB", (32, 32), (20, 40, 60)).save(p, format="JPEG")
print(p.resolve())
PY

REPORT_ID="<paste report_id from Step 8>"
curl -s -X POST "http://localhost:8000/api/v1/reports/${REPORT_ID}/images" \
  -H "Authorization: Bearer dev" \
  -F "file=@tmp_smoke.jpg;type=image/jpeg" \
  -F "is_primary=true"
```

**Pass if:** HTTP **201**; body has `image_id`, `has_vault: true`, `public_path: null` (blur is S4); `exif` has **no** `GPSInfo` / `gps_decimal` / `SerialNumber`.  
Check Supabase: row in `report_images` with `exif_json`; row in `image_vaults` with `vault_path` (never returned on this API).

**Fail if:** `415` wrong MIME · `413` too large · vault/API secrets in JSON.

---

## 17. Sprint 2 — Nearby (`ST_DWithin`)

```bash
make nearby-smoke
```

Or:

```bash
curl -s "http://localhost:8000/api/v1/reports/nearby?lat=6.9271&lon=79.8612&radius_m=5000" \
  -H "Authorization: Bearer dev"
```

**Pass if:** HTTP **200**; `count >= 1` after creating reports near Colombo; each item has `distance_m`; far points excluded if you insert one outside 5 km.

Optional far-point check (should not appear in 5 km query):

```bash
curl -s -X POST http://localhost:8000/api/v1/reports \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev" \
  -d "{\"report_type\":\"LOST\",\"title\":\"far away\",\"latitude\":7.2906,\"longitude\":80.6337}"
# Kandy ≈ 100 km from Colombo — should be absent from nearby at radius_m=5000
```

**Fail if:** empty when you just created a local report · `503` PostGIS/DB error.

---

## 18. Sprint 2 — Automated tests + sign-off

```bash
make test-sprint2
```

| # | Check | Required? | Pass means |
|---|---|---|---|
| S2-1 | Step 15 DB row | Yes | LOST/FOUND in `reports` with fuzzed location |
| S2-2 | Step 16 image upload | Yes | `report_images` + vault; public EXIF sanitized |
| S2-3 | Step 17 nearby | Yes | In-radius rows returned |
| S2-4 | `make test-sprint2` | Yes | Pytest green |
| S2-5 | Flutter GPS fields + fuzz | Recommended | Client fuzz before submit |

**Sprint 2 signed off when:** S2-1 + S2-2 + S2-3 + S2-4 pass.

Stop stack:

```bash
make down
```

---

## 13. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `uv not found` | uv not on PATH | Install uv; restart shell |
| `make` unknown | Not Git Bash / Make missing | Install Make or use Git Bash / WSL |
| `init-schema` / `test-db` fail | Wrong DB URL or port `5432` | Use pooler **6543**; check password URL-encoding |
| Health `db: offline` | Bad `SUPABASE_DB_URL` or network | Fix URL; confirm Supabase project healthy |
| Health `redis: offline` | Redis down or wrong host | `make up` / start redis; Docker → `REDIS_URL=redis://redis:6379/0` |
| `job_enqueued: false` | Arq off or Redis fail | Set `ARQ_WORKER_ENABLED=true`; fix `REDIS_URL`; restart API |
| Login always bypass | Placeholder Supabase URL/keys | Fill real keys; set `AUTH_DEV_BYPASS=false` |
| Login 401 (real Auth) | Bad user/password or anon key | Recreate user; copy `anon` key again |
| Report 401 | Bypass off + invalid JWT | Use valid token or `AUTH_DEV_BYPASS=true` |
| Report **503** | DB URL / schema / FK user | `make init-schema`; check `users` upsert; PostGIS enabled |
| Nearby empty | No rows with location / wrong coords | `make report-smoke` near query lat/lon |
| Image upload 415 | Not jpeg/png/webp | Use supported MIME |
| Flutter cannot reach API | Wrong base URL | Emulator: `10.0.2.2:8000`; device: PC LAN IP |
| Worker no stub log | Job never enqueued | Enable Arq on API + Redis online; re-POST report |
| Exact GPS in `reports` | Fuzz off? | Confirm `gps.fuzz_meters: 500` in `param.yaml`; server always re-fuzzes |

---

## 14. Quick copy-paste (happy path — S1 + S2)

Git Bash / WSL, from repo root, after `.env` P0 keys filled:

```bash
make env
make install
make init-schema
make test-db
make ensure-buckets
# set REDIS_URL=redis://redis:6379/0 and ARQ_WORKER_ENABLED=true in .env for Docker
make up
make health
curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"dev@example.com\",\"password\":\"password\"}"
make report-smoke          # persists + fuzzes
make nearby-smoke          # ST_DWithin
make logs-worker           # confirm process_report_ai line
make test-smoke
make test-sprint2
make down
```

---

## Notes

- Routes live under `/api/v1/…` except `/health`.
- **Never** commit `.env`. Public APIs never return vault paths, EXIF GPS, or `hidden_features`.
- Prefer diffs / `make` targets over ad-hoc global `pip install`.
- Secrets walkthrough: [`ENV_SETUP.md`](./ENV_SETUP.md). Product plan: [`FINAL_PROJECT_PLAN.md`](./FINAL_PROJECT_PLAN.md).
- Next: Sprint 3 dual AI pipeline (vision ∥ text embed + fusion).
