# VERIFIND AI — Core Execution Rules

- Source of truth: `docs/FINAL_PROJECT_PLAN.md`. Do not port voice/CRM/RAG from `Examples/` into MVP.
- Never expose vault originals or `hidden_features` on public APIs; public images must be sanitized.
- Prefer diffs / surgical edits; do not rewrite entire files.
- Minimize tool & test noise: compact flags, errors-only logs (e.g. `pytest -q`, `npm test -- --reporter=dot`).
- Secrets stay in env / secret stores; never commit `.env` or credentials.
- After code changes: run `graphify update .` (AST-only).
- Stack locked: FastAPI + LangGraph + MCP + Arq/Redis + PostGIS/pgvector + Flutter + React admin.
- don't commit `Examples` Folder into git