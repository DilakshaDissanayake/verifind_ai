-- VERIFIND Sprint 10 — nearby post alerts within 5 km
-- Additive; safe to re-run.
-- Stores a fuzzed last-known point so a new LOST/FOUND can notify users
-- currently in the area, without FCM or a device background service.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_location GEOGRAPHY(POINT, 4326);

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS last_location_at TIMESTAMPTZ;

CREATE INDEX IF NOT EXISTS idx_users_last_location
    ON users USING GIST (last_location);

COMMENT ON COLUMN users.last_location IS
    'Fuzzed device GPS for nearby-post alerts; never exact home/work';
COMMENT ON COLUMN users.last_location_at IS
    'When last_location was last updated; stale points are ignored';
