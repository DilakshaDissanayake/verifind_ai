-- VERIFIND Sprint 8 — private emergency contact for admin safety workflows
ALTER TABLE users
    ADD COLUMN IF NOT EXISTS emergency_contact TEXT;

COMMENT ON COLUMN users.emergency_contact IS
    'Private emergency contact; admin safety use only, never public API.';