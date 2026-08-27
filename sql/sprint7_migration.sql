-- VERIFIND Sprint 7 — Chat media + system analysis messages (idempotent)

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS message_type TEXT NOT NULL DEFAULT 'text';

ALTER TABLE chat_messages
    ADD COLUMN IF NOT EXISTS media_path TEXT;

DO $$ BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chat_messages_message_type_check'
  ) THEN
    ALTER TABLE chat_messages
      ADD CONSTRAINT chat_messages_message_type_check
      CHECK (message_type IN ('text', 'image', 'voice', 'system'));
  END IF;
END $$;

-- Media / system rows may use a short caption or placeholder body
COMMENT ON COLUMN chat_messages.message_type IS 'text | image | voice | system';
COMMENT ON COLUMN chat_messages.media_path IS 'public-sanitized storage path for image/voice';

CREATE INDEX IF NOT EXISTS idx_chat_messages_room_type
    ON chat_messages (room_id, message_type, created_at ASC);
