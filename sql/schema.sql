-- VERIFIND AI — MVP schema (Sprint 1–2)
-- Extensions: PostGIS + pgvector. Apply in Supabase SQL editor or migrate tool.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ---------------------------------------------------------------------------
-- Users (mirrors Supabase auth.users via id; app profile layer)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_user_id    UUID UNIQUE,
    email           TEXT UNIQUE NOT NULL,
    display_name    TEXT,
    emergency_contact TEXT,          
    role            TEXT NOT NULL DEFAULT 'user' CHECK (role IN ('user', 'admin')),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS trust_scores (
    user_id         UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    score           REAL NOT NULL DEFAULT 1.0 CHECK (score >= 0 AND score <= 1),
    claim_count_24h INT NOT NULL DEFAULT 0,
    fail_count      INT NOT NULL DEFAULT 0,
    lockout_until   TIMESTAMPTZ,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Reports + images + AI tags + vault
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS reports (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id),
    report_type     TEXT NOT NULL CHECK (report_type IN ('LOST', 'FOUND')),
    category        TEXT,
    title           TEXT,
    description     TEXT,
    status          TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'processing', 'active', 'matched', 'closed', 'flagged')),
    -- Fuzzed point used for matching (never expose precise home/work)
    location        GEOGRAPHY(POINT, 4326),
    location_label  TEXT,
    text_embedding  VECTOR(1536),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reports_location ON reports USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_reports_user ON reports (user_id);
CREATE INDEX IF NOT EXISTS idx_reports_type_status ON reports (report_type, status);

CREATE TABLE IF NOT EXISTS report_images (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id           UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    public_path         TEXT,          -- storage: public-sanitized (after S4 blur)
    content_type        TEXT,
    phash               BIGINT,
    hsv_histogram       JSONB,
    exif_json           JSONB,         -- full EXIF incl. GPS for forensics (never public API)
    is_primary          BOOLEAN NOT NULL DEFAULT FALSE,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_report_images_report_id ON report_images (report_id);

CREATE TABLE IF NOT EXISTS ai_tags (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id       UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    brand           TEXT,
    colors          TEXT[],
    category        TEXT,
    attributes      JSONB,
    mask_boxes      JSONB,             -- [{x,y,w,h}, ...]
    model           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Vault: originals + hidden_features — NEVER expose via public API / views
CREATE TABLE IF NOT EXISTS image_vaults (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_image_id UUID NOT NULL UNIQUE REFERENCES report_images(id) ON DELETE CASCADE,
    vault_path      TEXT NOT NULL,     -- storage: private-vault
    hidden_features JSONB,             -- admin / verify only
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ---------------------------------------------------------------------------
-- Matching / claims / verification / chat / notify / audit
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS matches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    lost_report_id  UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    found_report_id UUID NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    score           REAL NOT NULL,
    vision_score    REAL,
    text_score      REAL,
    geo_score       REAL,
    category_score  REAL,
    band            TEXT NOT NULL CHECK (band IN ('HIGH', 'MEDIUM', 'LOW')),
    notified_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (lost_report_id, found_report_id)
);

CREATE TABLE IF NOT EXISTS claim_attempts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id        UUID NOT NULL REFERENCES matches(id) ON DELETE CASCADE,
    claimant_id     UUID NOT NULL REFERENCES users(id),
    status          TEXT NOT NULL DEFAULT 'started'
                    CHECK (status IN ('started', 'passed', 'failed', 'review', 'blocked')),
    risk_score      REAL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS verification_sessions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    claim_attempt_id UUID NOT NULL REFERENCES claim_attempts(id) ON DELETE CASCADE,
    questions       JSONB NOT NULL DEFAULT '[]',
    answers         JSONB NOT NULL DEFAULT '[]',
    semantic_scores JSONB,
    overall_score   REAL,
    decision        TEXT CHECK (decision IN ('PASS', 'REVIEW', 'BLOCK', NULL)),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at    TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS chat_rooms (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id        UUID NOT NULL UNIQUE REFERENCES matches(id) ON DELETE CASCADE,
    owner_id        UUID NOT NULL REFERENCES users(id),
    finder_id       UUID NOT NULL REFERENCES users(id),
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id         UUID NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    sender_id       UUID NOT NULL REFERENCES users(id),
    body            TEXT NOT NULL DEFAULT '',
    message_type    TEXT NOT NULL DEFAULT 'text'
                    CHECK (message_type IN ('text', 'image', 'voice', 'system')),
    media_path      TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS notifications (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    chat_room_id    UUID REFERENCES chat_rooms(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_id        UUID REFERENCES users(id),
    action          TEXT NOT NULL,
    entity_type     TEXT,
    entity_id       UUID,
    meta            JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Nearby helper index note: use ST_DWithin(location, ST_MakePoint(lon,lat)::geography, 5000)

COMMENT ON TABLE image_vaults IS 'Private vault — do not expose vault_path or hidden_features on public APIs';
COMMENT ON COLUMN reports.location IS 'GPS-fuzzed geography for match queries only';

-- Sprint 9 additions live in sql/sprint9_admin_moderation.sql:
-- matches.admin_status, trust_scores.content_strike_count, moderation_events
