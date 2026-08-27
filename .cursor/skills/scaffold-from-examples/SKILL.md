---
name: scaffold-from-examples
description: Scaffold VERIFIND modules from Examples/ZuuSwarm-AI and medical-coice ai without porting voice CRM or RAG. Use when bootstrapping src layout, copying FastAPI/LangGraph/infra patterns, or starting Sprint 1 foundation.
---

# Scaffold from Examples

## Goal

Copy **structure and infra discipline** from `Examples/`, rewrite domain for lost/found + zero-fraud. Do **not** port voice, CRM tickets, or RAG/CAG chat product features.

## Steps

1. Read `docs/FINAL_PROJECT_PLAN.md` §§5–7, 12, 15 for locked layout and Week-1 actions.
2. Create target tree if missing:
   - `config/`, `sql/`, `src/{api,agents,pipelines,mcp_servers,services,infrastructure,workers}/`, `mobile/`, `ui/`, `tests/`, `docker/`
3. Port only these patterns from Examples:
   - FastAPI lifespan + routers + deps
   - LangGraph orchestrator + state + router
   - MCP stdio server skeleton
   - `llm_provider` + embeddings wrapper
   - Arq worker enqueue/tasks shell
   - YAML config loading
   - Loguru + Langfuse hooks
4. Strip: LiveKit/voice, hospital CRM, runbook RAG, multi-tier chat memory.
5. Rename prompts/tools to VERIFIND intents: intake / match / verify / fraud.
6. Smoke: `/health` green; stub `POST /reports` → 202 → worker log.
7. Run `graphify update .` after scaffolding.

## Checklist

- [ ] No vault data on public schemas
- [ ] `param.yaml` / `models.yaml` present with VERIFIND keys
- [ ] Examples copied as reference only — domain code is new
