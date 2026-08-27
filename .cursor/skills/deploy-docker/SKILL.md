---
name: deploy-docker
description: Build and run VERIFIND with Docker Compose, health checks, and later ECS-oriented layout. Use when adding Dockerfiles, compose files, CI deploy workflows, or production env wiring.
---

# Deploy Docker

## Services (MVP)

- `api` — FastAPI
- `worker` — Arq
- `redis` — queue + pub/sub
- Postgres/PostGIS via Supabase (managed) or local compose profile
- Optional `web` — React admin static/nginx

## Steps

1. Mirror `Examples/*/docker` + `compose*.yml` structure; strip voice containers.
2. Multi-stage Python image; non-root user; no secrets in image layers.
3. Inject env at runtime (`.env` / secrets manager); use `.env.example` as contract.
4. Health: `GET /health` for api; worker liveness via queue ping if available.
5. CI: build → push → deploy (OIDC → ECS later); keep GHA secrets out of logs.
6. Verify: api 202 on report stub; worker consumes job; admin UI reaches API.

## Do not

- Bake API keys into Dockerfiles
- Expose private-vault bucket publicly
- Enable medium-risk auto-PASS in prod before admin REVIEW ships
