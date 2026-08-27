-- VERIFIND Sprint 9 — admin match decide, content strikes, moderation queue
-- Additive; safe to re-run.

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS admin_status TEXT NOT NULL DEFAULT 'pending';

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS admin_note TEXT;

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS admin_decided_at TIMESTAMPTZ;

ALTER TABLE matches
    ADD COLUMN IF NOT EXISTS admin_decided_by UUID REFERENCES users(id);

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'matches_admin_status_check'
    ) THEN
        ALTER TABLE matches
            ADD CONSTRAINT matches_admin_status_check
            CHECK (admin_status IN ('pending', 'approved', 'rejected'));
    END IF;
END $$;

ALTER TABLE trust_scores
    ADD COLUMN IF NOT EXISTS content_strike_count INT NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS moderation_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind            TEXT NOT NULL
                    CHECK (kind IN (
                        'prohibited_content',
                        'content_strike',
                        'auto_block',
                        'admin_block',
                        'admin_unblock',
                        'contact_reveal',
                        'match_decide',
                        'report_resolve'
                    )),
    source          TEXT,
    snippet         TEXT,
    strike_number   INT,
    report_id       UUID REFERENCES reports(id) ON DELETE SET NULL,
    match_id        UUID REFERENCES matches(id) ON DELETE SET NULL,
    resolved        BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_by     UUID REFERENCES users(id),
    resolved_at     TIMESTAMPTZ,
    meta            JSONB NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_moderation_events_open
    ON moderation_events (resolved, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_moderation_events_user
    ON moderation_events (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_matches_admin_status
    ON matches (admin_status, band);

COMMENT ON TABLE moderation_events IS
    'Admin moderation trail: prohibited posts, strikes, blocks, contact reveals';
COMMENT ON COLUMN trust_scores.content_strike_count IS
    'Prohibited content attempts; 3 → auto block account';
COMMENT ON COLUMN matches.admin_status IS
    'Admin pass/reject for AI match suggestions; rejected hidden from users';
