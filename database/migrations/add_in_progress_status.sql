-- Run this migration to allow 'in_progress' status on the interviews table.
-- This is needed because the original CHECK constraint did not include it.
-- Only run this once if your DB was created from the old schema.

ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check;
ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
    CHECK (status IN ('scheduled','in_progress','completed','cancelled','expired'));
