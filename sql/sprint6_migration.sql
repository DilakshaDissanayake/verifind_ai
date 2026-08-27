-- VERIFIND Sprint 6 — Admin REVIEW harden (idempotent)
-- Index review queue; ensure audit_logs ready for admin decisions.

CREATE INDEX IF NOT EXISTS idx_claim_attempts_status
    ON claim_attempts (status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_verification_sessions_decision
    ON verification_sessions (decision)
    WHERE decision = 'REVIEW';

CREATE INDEX IF NOT EXISTS idx_audit_logs_entity
    ON audit_logs (entity_type, entity_id, created_at DESC);

-- Chat-ready notifications after admin PASS
ALTER TABLE notifications ADD COLUMN IF NOT EXISTS chat_room_id UUID REFERENCES chat_rooms(id) ON DELETE SET NULL;

-- Legacy `kind` was NOT NULL; keep it in sync with `type` so inserts don't fail
DO $$ BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'notifications' AND column_name = 'kind'
  ) THEN
    UPDATE notifications SET kind = COALESCE(kind, type, 'match_found') WHERE kind IS NULL;
    ALTER TABLE notifications ALTER COLUMN kind DROP NOT NULL;
    ALTER TABLE notifications ALTER COLUMN kind SET DEFAULT 'match_found';
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_notifications_chat_ready
    ON notifications (user_id, created_at DESC)
    WHERE type = 'chat_ready';

CREATE INDEX IF NOT EXISTS idx_notifications_user_unread
    ON notifications (user_id, created_at DESC)
    WHERE is_read = false;

-- Promote a local admin for demos (safe: only updates matching email / id).
-- Set AUTH_DEV_USER_ID email in app; run optionally after ensure_app_user.
-- UPDATE users SET role = 'admin' WHERE email = 'admin@verifind.local';

COMMENT ON INDEX idx_claim_attempts_status IS 'Sprint 6 admin REVIEW queue';
COMMENT ON COLUMN notifications.chat_room_id IS 'Set when type=chat_ready after PASS';
