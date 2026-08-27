# VERIFIND AI — Environment & Secrets Setup Guide

How to create your `.env`, and how to obtain **every** secret / API key step by step.

**Template file:** [`.env.example`](../.env.example)  
**After filling:** never commit `.env` (git-ignored).

```bash
make env          # copies .env.example → .env if missing
# then edit .env in an editor
```

---

## Priority for Sprint 1

| Priority | Keys | Needed for |
|---|---|---|
| **P0 — must** | Supabase URL, anon, service, JWT, DB URL (6543), Redis | Auth, DB, queue, health |
| **P1 — soon** | Storage buckets, `OPENAI_API_KEY` | Images / later AI pipeline |
| **P2 — optional** | OpenRouter, Groq, Anthropic, Google, Langfuse | Fallbacks + traces |
| **Dev only** | `AUTH_DEV_BYPASS=true` | Local smoke without real JWT |

---

## 1. Create the `.env` file

1. Open a terminal in the repo root (`verifind-ai`).
2. Run:
   ```bash
   make env
   ```
3. Open `.env` and replace every `replace-me` / `your-project` / `sk-replace-me` placeholder.
4. Save. Restart API/worker after changes (`make down && make up` or restart native processes).

---

## 2. Supabase (database, auth, storage)

**Dashboard:** [https://supabase.com/dashboard](https://supabase.com/dashboard)  
**Docs:** [https://supabase.com/docs](https://supabase.com/docs)

### 2.1 Create a project

1. Sign in / sign up at the dashboard.
2. **New project** → pick org, name (e.g. `verifind`), DB password (save it), region close to you.
3. Wait until the project is **Healthy**.

### 2.2 `SUPABASE_URL`

1. Open your project.
2. Go to **Project Settings** (gear) → **API**:  
   [https://supabase.com/dashboard/project/_/settings/api](https://supabase.com/dashboard/project/_/settings/api)
3. Copy **Project URL** (looks like `https://abcdefgh.supabase.co`).
4. Paste into `.env`:
   ```env
   SUPABASE_URL=https://abcdefgh.supabase.co
   ```

### 2.3 `SUPABASE_ANON_KEY`

Same page: **Project Settings → API**.

1. Under **Project API keys**, find **`anon` `public`**.
2. Reveal / copy the long JWT-looking string.
3. Paste:
   ```env
   SUPABASE_ANON_KEY=eyJhbGciOi...   # anon public
   ```
4. Safe to use in Flutter / browser clients (RLS still applies).

### 2.4 `SUPABASE_SERVICE_KEY`

Same page.

1. Find **`service_role` `secret`**.
2. Copy it.
3. Paste:
   ```env
   SUPABASE_SERVICE_KEY=eyJhbGciOi...   # service_role
   ```
4. **Never** put this in Flutter, React public builds, or GitHub. Server / workers only. Bypasses RLS.

### 2.5 `SUPABASE_JWT_SECRET`

1. Same **API** settings page → **JWT Settings**.
2. Copy **JWT Secret**.
3. Paste:
   ```env
   SUPABASE_JWT_SECRET=your-jwt-secret-here
   ```
4. Used by the API to verify Supabase access tokens.

### 2.6 `SUPABASE_DB_URL` (port **6543** pooler)

**Why 6543:** transaction-mode connection pooler. Direct **5432** caps ~15 clients on smaller plans.

**Docs:** [Connecting to Postgres (pooler)](https://supabase.com/docs/guides/database/connecting-to-postgres#supabase-connection-pooler)

1. **Project Settings → Database**:  
   [https://supabase.com/dashboard/project/_/settings/database](https://supabase.com/dashboard/project/_/settings/database)
2. Open **Connect** (or Connection string).
3. Choose:
   - Type: **URI**
   - Mode: **Transaction** pooler (Supavisor)
   - Port must be **6543**
4. Copy the URI. It looks like:
   ```text
   postgresql://postgres.<project-ref>:<YOUR-DB-PASSWORD>@aws-0-<region>.pooler.supabase.com:6543/postgres
   ```
5. Replace `[YOUR-PASSWORD]` with the **database password** you set at project creation (URL-encode special characters if needed, e.g. `@` → `%40`).
6. Paste into `.env` as `SUPABASE_DB_URL=...`

**Verify:**
```bash
make test-db
```

### 2.7 Storage buckets

**Names in `.env` (already set in example):**

```env
STORAGE_PUBLIC_BUCKET=public-sanitized
STORAGE_VAULT_BUCKET=private-vault
```

**Option A — CLI helper (needs valid `SUPABASE_URL` + service key):**
```bash
make ensure-buckets
```

**Option B — Dashboard:**  
[https://supabase.com/dashboard/project/_/storage/buckets](https://supabase.com/dashboard/project/_/storage/buckets)

1. **New bucket** → name `public-sanitized` → **Public** = ON.
2. **New bucket** → name `private-vault` → **Public** = OFF.
3. Keep names exactly as in `.env`.

**Schema (tables):** after DB URL works:
```bash
make init-schema
```

---

## 3. Redis (queue for Arq workers)

**Local with Docker Compose (recommended):**  
Install [Docker Desktop](https://docs.docker.com/desktop/), then `make up` starts Redis for you.

```env
# From your host machine (API/worker on host, Redis in compose):
REDIS_URL=redis://localhost:6379/0

# If the API process runs *inside* the compose network, use:
# REDIS_URL=redis://redis:6379/0
```

**Docs:** [Install Redis](https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/)

```env
ARQ_WORKER_ENABLED=false   # true when you want enqueue → worker in prod-like local runs
```

For Docker worker service, compose already sets worker enable. For native `make worker`, set `ARQ_WORKER_ENABLED=true` in `.env` or rely on the Makefile target.

---

## 4. API process settings (no secrets)

Defaults are fine for local:

```env
API_HOST=0.0.0.0
API_PORT=8000
API_RELOAD=true
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
LOG_LEVEL=INFO
```

- Change `CORS_ORIGINS` when you add admin UI / Flutter web origins.
- `API_PORT` must match what you curl / Flutter points at (`http://localhost:8000`).

---

## 5. LLM / AI API keys

Sprint 1 soft-attaches LLMs; **OpenAI** is enough to start. Others are circuit-breaker fallbacks (later sprints).

### 5.1 `OPENAI_API_KEY` (primary)

1. Create / sign in: [https://platform.openai.com](https://platform.openai.com)
2. Add billing if required: [https://platform.openai.com/settings/organization/billing](https://platform.openai.com/settings/organization/billing)
3. Open **API keys**: [https://platform.openai.com/api-keys](https://platform.openai.com/api-keys)
4. **Create new secret key** → copy once (`sk-...`).
5. Paste:
   ```env
   OPENAI_API_KEY=sk-proj-...
   ```
6. Docs: [https://platform.openai.com/docs/quickstart](https://platform.openai.com/docs/quickstart)

### 5.2 `OPENROUTER_API_KEY` (optional fallback)

1. [https://openrouter.ai](https://openrouter.ai) → sign up.
2. Keys: [https://openrouter.ai/keys](https://openrouter.ai/keys)
3. Create key → paste `OPENROUTER_API_KEY=...`
4. Docs: [https://openrouter.ai/docs](https://openrouter.ai/docs)

### 5.3 `GROQ_API_KEY` (optional)

1. [https://console.groq.com](https://console.groq.com)
2. Keys: [https://console.groq.com/keys](https://console.groq.com/keys)
3. Create API key → `GROQ_API_KEY=...`
4. Docs: [https://console.groq.com/docs](https://console.groq.com/docs)

### 5.4 `ANTHROPIC_API_KEY` (optional — Claude)

1. [https://console.anthropic.com](https://console.anthropic.com)
2. Keys: [https://console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys)
3. Create key → `ANTHROPIC_API_KEY=sk-ant-...`
4. Docs: [https://docs.anthropic.com](https://docs.anthropic.com)

### 5.5 `GOOGLE_API_KEY` (optional — Gemini)

1. Google AI Studio: [https://aistudio.google.com/apikey](https://aistudio.google.com/apikey)
2. **Create API key** → paste `GOOGLE_API_KEY=...`
3. Docs: [https://ai.google.dev/gemini-api/docs](https://ai.google.dev/gemini-api/docs)

---

## 6. Langfuse (optional — LLM traces)

1. Sign up: [https://cloud.langfuse.com](https://cloud.langfuse.com)
2. Create a project.
3. **Settings → API Keys** → create / copy **Secret** + **Public**.
4. Paste:
   ```env
   LANGFUSE_SECRET_KEY=sk-lf-...
   LANGFUSE_PUBLIC_KEY=pk-lf-...
   LANGFUSE_HOST=https://cloud.langfuse.com
   ```
5. Docs: [https://langfuse.com/docs/get-started](https://langfuse.com/docs/get-started)

> Examples repos sometimes use `LANGFUSE_BASE_URL`. VERIFIND code reads **`LANGFUSE_HOST`**.

---

## 7. Auth dev bypass (local only)

```env
AUTH_DEV_BYPASS=true
AUTH_DEV_USER_ID=00000000-0000-0000-0000-000000000001
AUTH_DEV_EMAIL=dev@verifind.local
```

| Value | Meaning |
|---|---|
| `true` | Login returns a fake token when Supabase keys are still placeholders — good for `make test-smoke` / early S1 |
| `false` | Real Supabase email/password login — set after anon key + Auth users exist |

**Create a real user (when bypass is off):**  
Dashboard → **Authentication** → **Users** → Add user:  
[https://supabase.com/dashboard/project/_/auth/users](https://supabase.com/dashboard/project/_/auth/users)

---

## 8. What we deliberately do **not** put in VERIFIND `.env`

Copied from Examples apps but **out of MVP** (see `docs/FINAL_PROJECT_PLAN.md`):

| Examples key | Why omitted |
|---|---|
| `QDRANT_*` | RAG; Phase 2 optional |
| `TAVILY_API_KEY` | Web-search chat |
| `LIVEKIT_*` / `DEEPGRAM_*` / `ELEVEN_API_KEY` | Voice pipeline |

---

## 9. Security checklist

- [ ] `.env` is not staged/committed (`git status` clean of `.env`)
- [ ] `SUPABASE_SERVICE_KEY` only on server / Docker secrets
- [ ] Vault bucket stays **private**
- [ ] Rotate any key that was pasted into chat, screenshots, or tickets
- [ ] Production: `AUTH_DEV_BYPASS=false`

---

## 10. Verify everything

Follow the short checklist: [`SPRINT1_TEST.md`](./SPRINT1_TEST.md)

```bash
make status
make test-db
make up
make health
make report-smoke
make test-smoke
```

---

## Quick link index

| Need | Link |
|---|---|
| Supabase dashboard | https://supabase.com/dashboard |
| Supabase API keys | https://supabase.com/dashboard/project/_/settings/api |
| Supabase database / pooler | https://supabase.com/dashboard/project/_/settings/database |
| Supabase pooler docs | https://supabase.com/docs/guides/database/connecting-to-postgres#supabase-connection-pooler |
| Supabase storage | https://supabase.com/dashboard/project/_/storage/buckets |
| Supabase Auth users | https://supabase.com/dashboard/project/_/auth/users |
| Docker Desktop | https://docs.docker.com/desktop/ |
| Redis docs | https://redis.io/docs/latest/operate/oss_and_stack/install/install-redis/ |
| OpenAI API keys | https://platform.openai.com/api-keys |
| OpenRouter keys | https://openrouter.ai/keys |
| Groq keys | https://console.groq.com/keys |
| Anthropic keys | https://console.anthropic.com/settings/keys |
| Google AI Studio key | https://aistudio.google.com/apikey |
| Langfuse Cloud | https://cloud.langfuse.com |
| Langfuse docs | https://langfuse.com/docs/get-started |
