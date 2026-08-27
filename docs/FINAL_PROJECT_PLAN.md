# VERIFIND AI — Final Project Plan

**Product:** Intelligent Zero-Fraud Lost & Found Matchmaking System  
**Source of truth for ideas:** `docs/mybrainstromidea.md`  
**Scaffold inspiration:** `Examples/ZuuSwarm-AI` + `Examples/medical-coice ai`  
**Status:** Approved direction for implementation (idea → build plan)

---

## 1. One-line thesis

Build a lost-and-found platform where **finders upload photos, the system hides unique identifiers, AI matches nearby lost/found reports, and claimants must prove ownership via adversarial questions** — so fraud (guessing from public photos) becomes impractical.

---

## 2. Problem → Solution map

| Pain today | VERIFIND answer |
|---|---|
| Public photos enable fake claims | Visual Evidence Vault + Gaussian-blurred public images |
| Exact GPS leaks home/work | **Device GPS** (OS location permission) → client-side fuzz (±500 m) before upload; server re-fuzzes; **product UI never asks users to type lat/lon** |
| Manual matching does not scale | Dual AI pipeline + PostGIS + multimodal fusion |
| Single LLM outage kills the app | Circuit-breaker model tiers (OpenAI → Gemini/Claude → local) |

**Core research contribution (must ship):** 4-Layer Zero-Fraud Shield  
Vault → Metadata forensics → Interrogation → Behavioral risk scoring.

---

## 3. What we reuse from the Examples (do not reinvent)

Both example apps already prove a production pattern. VERIFIND should **copy structure, rewrite domain logic**.

| Pattern from Examples | Where it lives | VERIFIND use |
|---|---|---|
| FastAPI app + lifespan warmup | `src/api/main.py` | API gateway, JWT deps, health |
| LangGraph `AgentOrchestrator` + `AgentState` | `src/agents/orchestrator.py`, `state.py` | Intake → Matchmaker → Verification graph |
| Router / decision graph | `router.py`, `decision_graph.py` | Route LOST vs FOUND vs CLAIM intents |
| MCP stdio tool servers | `src/mcp_servers/*` | Vision, Report, Geo, Fraud, Chat servers |
| YAML config | `config/param.yaml`, `models.yaml` | Fusion weights, thresholds, model tiers |
| Multi-provider LLM wrapper | `infrastructure/llm/llm_provider.py` | Vision / verify / embed fallbacks |
| Arq + Redis workers | `src/workers/tasks.py` | `process_report_ai`, `compute_matches` |
| Supabase Auth + SQL | `infrastructure/db/*` | Users, RLS, storage buckets |
| pgvector / Qdrant | embeddings + vector clients | Text similarity candidates |
| Langfuse + Loguru | `observability.py`, `log.py` | Trace every LLM / pipeline step |
| Docker + GHA OIDC → ECS | `compose*.yml`, `.github/workflows` | Deploy `api` + `worker` (+ optional `web`) |
| React SPA shell | `ui/` | **Admin fraud dashboard** (not chat-first UI) |

### Explicitly **out of MVP** (examples have them; VERIFIND does not need them yet)

- LiveKit / Deepgram / ElevenLabs **voice**
- Hospital CRM / IT incident tickets
- RAG runbooks / CAG cache for chat Q&A
- 4-tier conversational memory (ST/LT/EP/Procedural) as a chat product

Those are inspiration for *architecture discipline*, not features to port.

---

## 4. VERIFIND-unique modules (must build)

```
pipelines/
  vision_pipeline.py          # gpt-4o-mini: category, brand, colors, mask boxes
  text_pipeline.py            # parse + text-embedding-3-small
  sanitization_pipeline.py    # Pillow blur → public / vault split
  metadata_pipeline.py        # EXIF + pHash + HSV histogram
  fusion.py                   # α·vision + β·text + γ·geo + δ·category
  verification_pipeline.py    # adversarial Q gen + semantic scoring
  fraud_pipeline.py           # velocity, cooldown, device, geo anomaly
  dual_executor.py            # asyncio.gather vision ∥ text

mcp_servers/
  vision_server.py | report_server.py | geo_server.py | fraud_server.py | chat_server.py

mobile/                       # Flutter Clean Architecture (not in Examples)
ui/                           # React Admin (fraud review queue)
```

---

## 5. Target architecture (locked)

```
Flutter App ──HTTPS/WSS──▶ Nginx/ALB ──▶ FastAPI
                              │
                              ├─ LangGraph Orchestrator
                              │     Intake → Matchmaker → Verification
                              │           │
                              │     MCP: Vision | Report | Geo | Fraud | Chat
                              │
                              ├─ Arq Worker (Redis)
                              │     process_report_ai → compute_matches → notify
                              │
                              └─ Data
                                    Supabase PG + PostGIS + pgvector
                                    Supabase Storage (public-sanitized | private-vault)
                                    Redis (queue + chat pub/sub)
                                    Qdrant optional (primary vectors; PG fallback)
```

### Agent graph (final)

1. **Supervisor / Router** — classify payload: report intake / match refresh / claim verify  
2. **Report Intake Agent** — taxonomy + mask regions + enqueue dual pipeline  
3. **Matchmaker Agent** — `ST_DWithin` ≤ 5 km → fusion score → notify if ≥ 0.80  
4. **Verification Agent** — vault features → questions → score → fraud risk → PASS / REVIEW / BLOCK  

### Match formula (defaults in `param.yaml`)

`Score = 0.30·Vision + 0.30·Text + 0.25·Geo + 0.15·Category`  
HIGH ≥ 0.80 · MEDIUM 0.50–0.79 · LOW < 0.50

### Mobile location UX (Sprint 2 — locked)

Product path (required):

1. App requests OS location permission.  
2. Read **device GPS** (current position).  
3. Apply client fuzz ±500 m (`config/param.yaml` → `gps.fuzz_meters`).  
4. Send fuzzed coordinates on Create Report / Nearby — **never show editable lat/lon text fields** as the normal UX.  
5. Server may re-fuzz before PostGIS insert (defense in depth).  

Allowed only for engineers / curl / Makefile smoke: typing lat/lon in API clients. That is **not** the Flutter product UI.

### Fraud decisions

| Risk | Action |
|---|---|
| < 0.3 | PASS → anonymous chat room |
| 0.3 – 0.7 | REVIEW → admin queue |
| ≥ 0.7 | BLOCK → flag + trust penalty |

---

## 6. Product scope (MVP vs later)

### MVP (must ship for demo / thesis)

1. Auth (Supabase JWT)  
2. Lost + Found report create (photo, text, **device GPS** fuzzed ±500 m — **no manual lat/lon product UI**)  
3. Async AI: vision + embed + sanitize + vault  
4. Spatial + multimodal matching + FCM/in-app notify  
5. Claim → 3 adversarial questions → semantic score  
6. Behavioral fraud gate (velocity + fail cooldown minimum)  
7. Anonymous WebSocket chat on PASS  
8. Admin: fraud REVIEW queue (side-by-side vault vs public)  
9. Basic Langfuse traces + health endpoint  

### Phase 2 (after MVP works end-to-end)

- Full device fingerprint rings, geo-anomaly, trust score UI  
- Qdrant primary + pgvector fallback polish  
- Full multi-provider circuit breakers (Gemini / Claude / Ollama)  
- Report history UX polish, GDPR purge  
- ECS Fargate production deploy  

### Phase 3 (optional polish)

- Advanced admin health HUD / circuit overrides  
- Offline OpenCV/Tesseract vision fallback  
- Extra categories, multi-image reports  

---

## 7. Repo layout (final target)

Mirror Examples layout so copy-paste of infra stays easy:

```
verifind-ai/
├── config/param.yaml
├── config/models.yaml
├── sql/schema.sql                 # PostGIS + pgvector + app tables
├── src/
│   ├── api/                       # FastAPI routers
│   ├── agents/                    # LangGraph orchestrator
│   ├── pipelines/                 # VERIFIND AI core
│   ├── mcp_servers/
│   ├── services/
│   ├── infrastructure/
│   └── workers/
├── mobile/                        # Flutter
├── ui/                            # React admin
├── tests/
├── docker/ + compose*.yml
└── .github/workflows/
```

---

## 8. Data model (minimal entities)

Implement first from brainstorm ERD:

`users` · `trust_scores` · `reports` · `report_images` · `ai_tags` · `image_vaults` · `matches` · `claim_attempts` · `verification_sessions` · `chat_rooms` · `chat_messages` · `notifications` · `audit_logs`

Storage buckets:

- `public-sanitized` — what claimants see  
- `private-vault` — original + hidden_features JSON (never public API)

---

## 9. Sprint plan (12 weeks → 6 sprints)

| Sprint | Weeks | Goal | Exit criteria |
|---|---|---|---|
| **S1 Foundation** | 1–2 | Scaffold from Examples: FastAPI, config, Supabase Auth, schema, Flutter shell, OpenAI wrapper | Login works; empty `/health` green |
| **S2 Reports + Geo** | 3–4 | Report CRUD, image upload, **device GPS** (±500 m client fuzz, never manual lat/lon typing in product UI), PostGIS `ST_DWithin`, EXIF extract, Flutter: Create Report + Nearby from phone location | Create LOST/FOUND with auto GPS; nearby query returns rows on device |
| **S3 AI dual pipeline** | 5–6 | Vision + text embed + Arq worker + fusion | New report → tags + embedding within ≤8s budget |
| **S4 Zero-Fraud L1–L2** | 7–8 | Mask + blur + vault + pHash + match notify | Public image blurred; vault private; HIGH match notifies |
| **S5 Verify + Chat** | 9–10 | Interrogation + scoring + fraud gate + WSS chat | PASS unlocks chat; BLOCK rejects |
| **S6 Admin + Harden** | 11–12 | React REVIEW queue, tests ≥80% core paths, Langfuse, CI | End-to-end demo script passes |

---

## 10. Build order inside each vertical (dependency rules)

1. **Schema + storage buckets** before any pipeline  
2. **Vision + sanitization** before match notifications (never show raw unique IDs)  
3. **Matchmaker** before claim UI  
4. **Verification** before chat provisioning  
5. **Admin REVIEW** before enabling medium-risk auto-pass in prod  

Never short-circuit: public feed must never receive vault originals.

---

## 11. Non-functional targets (demo-grade)

| Metric | Target |
|---|---|
| Report create API | ≤ 200 ms (202 Accepted) |
| Full AI pipeline | ≤ 8 s |
| PostGIS nearby | ≤ 50 ms |
| Claim velocity | ≤ 3 / 24 h |
| Fail lockout | 3 fails → 24 h |
| pHash near-dup | Hamming ≤ 5 → flag |

---

## 12. Tech stack (locked for this project)

| Layer | Choice |
|---|---|
| Mobile | Flutter 3.x (BLoC + Dio) |
| API | Python 3.11 + FastAPI |
| Agents | LangGraph StateGraph |
| Tools | MCP stdio servers |
| Vision | gpt-4o-mini (primary) |
| Verify | gpt-4o (primary) |
| Embed | text-embedding-3-small (1536d) |
| DB | Supabase PostgreSQL + PostGIS + pgvector |
| Queue | Redis + Arq |
| Admin | React SPA |
| Observability | Langfuse + Loguru |
| Deploy | Docker → (later) AWS ECS Fargate |

Provider routing: prefer Examples’ OpenRouter-style `models.yaml` tiers for fallbacks, while keeping native OpenAI as primary for vision quality.

---

## 13. Demo script (definition of done)

1. Finder uploads laptop photo with sticker → public image shows sticker blurred.  
2. Owner submits lost report nearby → HIGH match push arrives.  
3. Owner claims → answers sticker/damage questions correctly → PASS → chat opens as Owner/Finder.  
4. Second account guesses vaguely → FAIL / BLOCK or REVIEW.  
5. Admin opens REVIEW item → sees vault original vs public side-by-side.  

If this path works, the thesis innovation is proven.

---

## 14. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Vision misses stickers | Prompt + JSON schema force; allow multi-region masks; admin override |
| Fusion false positives | Category hard gate + geo radius; tunable `param.yaml` |
| LLM cost / rate limits | mini for intake; 4o only for verify; Arq queue + circuit breakers |
| Scope creep (voice, RAG chat) | Stick to MVP list in §6 |
| Flutter + backend parallel lag | Contract-first OpenAPI; mock match responses week 2 |

---

## 15. Immediate next actions (Week 1)

1. Scaffold `src/` from ZuuSwarm/medical layout (strip voice/CRM/RAG).  
2. Write `sql/schema.sql` for MVP tables + PostGIS + pgvector.  
3. Create Supabase project: Auth, `public-sanitized`, `private-vault`.  
4. Port `llm_provider` + `param.yaml` / `models.yaml` with VERIFIND keys (fusion, fraud thresholds).  
5. Flutter: auth + Create Report (**device GPS** + photo) + Nearby from phone location — never ship manual lat/lon fields as the product path.  
6. Smoke: `POST /reports` → 202 → worker stub logs job.

---

## 16. Document relationship

| Doc | Role |
|---|---|
| `docs/mybrainstromidea.md` | Full idea dump / diagrams / FR-NFR matrix (reference) |
| `docs/FINAL_PROJECT_PLAN.md` | **This file — execution plan** |
| `docs/TEST_PLAN.md` | Test plan + test-case tables + evidence columns (S1–S6 / E2E) |
| `docs/SPRINT1_TEST.md` | Sprint 1–2 live configure & smoke how-to |
| `docs/ENV_SETUP.md` | Secrets / API key walkthrough |
| `docs/PRODUCTION_EXECUTION.md` | Production-like / demo-prod bring-up, hardening, ops |
| `README.md` | Public product summary |

Brainstorm stays the detailed design bible. This plan is what you build against sprint-by-sprint.
