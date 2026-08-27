---
name: db-schema-migrate
description: Create or migrate VERIFIND Postgres schema with PostGIS, pgvector, RLS-friendly tables, and storage bucket assumptions. Use when editing sql/, Supabase schema, indexes, or embedding columns.
---

# DB Schema & Migrate

## Order

1. Extensions: `postgis`, `vector`
2. Core tables from plan §8 (users → reports → vaults → matches → claims → chat → audit)
3. Indexes: spatial (`GIST` on geography), vector (ivfflat/hnsw as appropriate), FK lookups
4. RLS policies aligned with Supabase roles
5. Storage buckets (app config, not SQL): `public-sanitized`, `private-vault`

## Conventions

- Additive migrations preferred; never drop `image_vaults` casually.
- Embeddings: `vector(1536)` for OpenAI small embed.
- Geo: store fuzzed point used for match; document if raw GPS retained server-side (prefer not).
- Vault metadata / `hidden_features` not exposed via public views.

## Checklist

- [ ] `ST_DWithin` nearby query works ≤5 km
- [ ] Vector similarity query path defined (PG primary or Qdrant + PG fallback)
- [ ] Audit log table writable from API/workers
- [ ] Run migrate in staging before prod
