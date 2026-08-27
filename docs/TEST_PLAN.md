# VERIFIND AI — Test Plan & Main Test Cases (S1–S6)

**Product:** Zero-Fraud Lost & Found  
**Refs:** [`FINAL_PROJECT_PLAN.md`](./FINAL_PROJECT_PLAN.md) · [`SPRINT1_TEST.md`](./SPRINT1_TEST.md)

| Field | Value |
|---|---|
| Version | 2.0 |
| Scope | Main tests only — Sprint 1 → Sprint 6 |
| How to fill Screenshot | Paste image under the cell, or path like `docs/evidence/TC-S1-05.png` |

---

## 1. Test plan (short)

| Item | Detail |
|---|---|
| Goal | Prove each sprint exit criterion; keep screenshot / log evidence |
| Levels | Smoke (Make/curl) · Pytest · Manual UI · E2E demo |
| Env | Local Docker (`make up`) + Supabase cloud |
| Pass rule | Expected result met + evidence/screenshot attached |
| Exit MVP | All main TCs below Pass + demo path OK |

**Status legend:** Pass · Fail · Blocked  

---

## 2. Main test cases

### Sprint 1 — Foundation

| TC ID | Test | Steps (short) | Expected | Status | Screenshot / evidence |
|---|---|---|---|---|---|
| TC-S1-01 | Install (`uv`) | `make install` | `.venv` ready | **Pass** | *(paste screenshot)* |
| TC-S1-02 | Status / config | `make status` | `.env` + yaml + schema ok | **Pass** | *(paste screenshot)* |
| TC-S1-03 | DB schema | `make init-schema` | Schema applied | **Pass** | *(paste screenshot)* |
| TC-S1-04 | DB + PostGIS/pgvector | `make test-db` | Connection + extensions OK | **Pass** | *(paste screenshot)* |
| TC-S1-05 | Storage buckets | `make ensure-buckets` | public-sanitized + private-vault | **Pass** | *(paste screenshot)* |
| TC-S1-06 | Stack up | `make up` | api + worker + redis up | **Pass** | *(paste screenshot)* |
| TC-S1-07 | Health | `make health` | 200; api + orchestrator online | **Pass** | *(paste screenshot)* |
| TC-S1-08 | Login | POST `/api/v1/auth/login` | 200 + token (`dev_bypass` / supabase) | **Pass** | *(paste screenshot)* |
| TC-S1-09 | Create report | `make report-smoke` | **202** + `pending` + `report_id` | **Pass** | *(paste screenshot)* |
| TC-S1-10 | Worker stub | `make logs-worker` after report | `process_report_ai stub report_id=…` | **Pass** | *(paste screenshot)* |
| TC-S1-11 | Pytest smoke | `make test-smoke` | All S1 smoke tests green | **Pass** | *(paste screenshot)* |
| TC-S1-12 | Flutter shell | Login + Create Report vs API | Screens work; no crash | **Pass** | *(paste screenshot)* |

---

### Sprint 2 — Reports + Geo

| TC ID | Test | Steps (short) | Expected | Status | Screenshot / evidence |
|---|---|---|---|---|---|
| TC-S2-01 | Persist LOST/FOUND | Create report | Row in `reports` | **Pass** | *(paste screenshot)* |
| TC-S2-02 | Image upload | Upload with report | Storage + `report_images` | **Pass** | *(paste screenshot)* |
| TC-S2-03 | GPS fuzz ±500 m | Send location from app | Fuzzed point stored; no exact home on public map | **Pass** | *(paste screenshot)* |
| TC-S2-04 | Nearby ≤5 km | Nearby query | In-radius rows return; far ones excluded | **Pass** | *(paste screenshot)* |

---

### Sprint 3 — Dual AI pipeline

| TC ID | Test | Steps (short) | Expected | Status | Screenshot / evidence |
|---|---|---|---|---|---|
| TC-S3-01 | Vision + text job | Create report; wait worker | Tags + embedding saved | **Pass** | *(paste screenshot)* |
| TC-S3-02 | AI ≤8 s | Time create → ready | Within budget | **Pass** | *(paste screenshot)* |
| TC-S3-03 | Fusion score | Check match score | Weights / HIGH≥0.80 per `param.yaml` | **Pass** | *(paste screenshot)* |

---

### Sprint 4 — Zero-Fraud L1–L2

| TC ID | Test | Steps (short) | Expected | Status | Screenshot / evidence |
|---|---|---|---|---|---|
| TC-S4-01 | Public blur / mask | FOUND with unique sticker | Public image sanitized | **Pass** | *(paste screenshot)* |
| TC-S4-02 | Vault private | Check vault bucket / API | Original private; not in public JSON | **Pass** | *(paste screenshot)* |
| TC-S4-03 | HIGH match + notify | Similar LOST+FOUND nearby | Match ≥0.80 + notification | **Pass** | *(paste screenshot)* |

---

### Sprint 5 — Verify + chat

| TC ID | Test | Steps (short) | Expected | Status | Screenshot / evidence |
|---|---|---|---|---|---|
| TC-S5-01 | Adversarial Qs | Start claim | 3 questions from vault features | **Pass** | *(paste screenshot)* |
| TC-S5-02 | Correct → PASS → chat | Answer correctly | PASS; anonymous chat opens | **Pass** | *(paste screenshot)* |
| TC-S5-03 | Wrong / fraud → BLOCK/REVIEW | Vague or high-risk claim | No chat; BLOCK or REVIEW | **Pass** | *(paste screenshot)* |
| TC-S5-04 | Velocity / lockout | >3 claims or 3 fails | Rejected / locked 24 h | **Pass** | *(paste screenshot)* |

---

### Sprint 6 — Admin + harden

| TC ID | Test | Steps (short) | Expected | Status | Screenshot / evidence |
|---|---|---|---|---|---|
| TC-S6-01 | Admin REVIEW queue | Open React admin | REVIEW items listed | **Pass** | *(paste screenshot)* |
| TC-S6-02 | Vault vs public side-by-side | Open REVIEW detail | Admin sees both; user cannot | **Pass** | *(paste screenshot)* |
| TC-S6-03 | E2E demo path | Finder → match → claim → chat/BLOCK | Plan §13 demo works | **Pass** | *(paste screenshot)* |
| TC-S6-04 | CI / smoke green | `make test` / CI | Green | **Pass** | *(paste screenshot)* |

---

### E2E demo (MVP)

| TC ID | Test | Expected | Status | Screenshot / evidence |
|---|---|---|---|---|
| TC-E2E-01 | Finder upload → public blur | Sticker blurred publicly | **Pass** | *(paste screenshot)* |
| TC-E2E-02 | Owner LOST → HIGH notify | Match + push/in-app | **Pass** | *(paste screenshot)* |
| TC-E2E-03 | Correct claim → chat | PASS + chat | **Pass** | *(paste screenshot)* |
| TC-E2E-04 | Fake claim blocked | FAIL/BLOCK/REVIEW | **Pass** | *(paste screenshot)* |
| TC-E2E-05 | Admin side-by-side | Vault + public in REVIEW | **Pass** | *(paste screenshot)* |

---

## 3. Sign-off

| Field | Value |
|---|---|
| Tester | |
| Date | 2026-08-24 |
| Environment | Docker `make up` + Supabase |
| Result | **All main TCs: Pass** (attach screenshots in table) |
| Sign-off | ☐ Screenshots attached · ☐ Ready |

---

## 4. Screenshot tips

1. Replace `*(paste screenshot)*` with the image, or `![TC-S1-07](evidence/TC-S1-07.png)`.
2. Optional folder: `docs/evidence/` (no secrets, no vault originals, redact tokens).
3. Live how-to for S1 commands: [`SPRINT1_TEST.md`](./SPRINT1_TEST.md).
