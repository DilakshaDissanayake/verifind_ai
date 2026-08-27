-- VERIFIND Sprint 4-5 Migration (Postgres / Supabase compatible)
-- Safe to run multiple times.

-- ---------------------------------------------------------------------------
-- Fix matches table: rename lost/found cols → report_a/b, add missing cols
-- ---------------------------------------------------------------------------

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'matches'
      AND column_name = 'lost_report_id'
  ) THEN
    ALTER TABLE matches RENAME COLUMN lost_report_id  TO report_a_id;
    ALTER TABLE matches RENAME COLUMN found_report_id TO report_b_id;
  END IF;
END $$;

ALTER TABLE matches DROP CONSTRAINT IF EXISTS matches_lost_report_id_found_report_id_key;

-- Postgres has no ADD CONSTRAINT IF NOT EXISTS — use a DO block
DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'matches_pair_unique'
  ) THEN
    ALTER TABLE matches
      ADD CONSTRAINT matches_pair_unique UNIQUE (report_a_id, report_b_id);
  END IF;
END $$;

ALTER TABLE matches ADD COLUMN IF NOT EXISTS distance_m REAL;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS notified   BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE matches ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'matches'
      AND column_name = 'notified_at'
  ) THEN
    ALTER TABLE matches DROP COLUMN notified_at;
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Fix notifications table
-- ---------------------------------------------------------------------------

ALTER TABLE notifications ADD COLUMN IF NOT EXISTS type              TEXT DEFAULT 'match_found';
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS match_id          UUID REFERENCES matches(id) ON DELETE SET NULL;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS report_id         UUID REFERENCES reports(id) ON DELETE SET NULL;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS matched_report_id UUID REFERENCES reports(id) ON DELETE SET NULL;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS band              TEXT;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS score             REAL;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS distance_m        REAL;
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS is_read           BOOLEAN NOT NULL DEFAULT false;

-- Backfill type if null
UPDATE notifications SET type = COALESCE(type, 'match_found') WHERE type IS NULL;

DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'notifications'
      AND column_name = 'kind'
  ) AND NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public'
      AND table_name = 'notifications'
      AND column_name = 'type'
  ) THEN
    ALTER TABLE notifications RENAME COLUMN kind TO type;
  END IF;
END $$;

-- ---------------------------------------------------------------------------
-- Claim / verification columns
-- ---------------------------------------------------------------------------

ALTER TABLE claim_attempts ADD COLUMN IF NOT EXISTS fraud_risk REAL;
ALTER TABLE claim_attempts ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT now();

ALTER TABLE verification_sessions ADD COLUMN IF NOT EXISTS vault_features JSONB;

-- ---------------------------------------------------------------------------
-- Chat tables
-- ---------------------------------------------------------------------------

CREATE TABLE IF NOT EXISTS chat_rooms (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    match_id    UUID NOT NULL UNIQUE REFERENCES matches(id) ON DELETE CASCADE,
    owner_id    UUID NOT NULL REFERENCES users(id),
    finder_id   UUID NOT NULL REFERENCES users(id),
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS chat_messages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id     UUID NOT NULL REFERENCES chat_rooms(id) ON DELETE CASCADE,
    sender_id   UUID NOT NULL REFERENCES users(id),
    body        TEXT NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_room ON chat_messages (room_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_notifications_user ON notifications (user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_claim_attempts_claimant ON claim_attempts (claimant_id, created_at DESC);

-- ---------------------------------------------------------------------------
-- RLS: enable, no public policies (backend uses service role)
-- ---------------------------------------------------------------------------

ALTER TABLE chat_rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE chat_messages ENABLE ROW LEVEL SECURITY;
