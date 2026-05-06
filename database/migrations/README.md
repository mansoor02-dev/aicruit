# Migrations (historical)

These SQL files are kept for **history only**. They have all been folded into
[`../schema.sql`](../schema.sql), which is now the single source of truth and
is fully idempotent.

## What this means

- For a **fresh** database, run `database/schema.sql` once via `init_db.py`
  (or directly with `psql -f`). All tables, columns, constraints, indexes
  and the kanban-stages backfill are created in one pass.
- For an **existing** database, re-running `database/schema.sql` is safe.
  Every block in the "FOLDED MIGRATIONS" section at the bottom of the file
  uses `CREATE ... IF NOT EXISTS`, `ADD COLUMN IF NOT EXISTS`, or a
  `DO $$ ... $$` guard that checks `pg_constraint` /
  `information_schema.columns` before mutating anything.
- You should **not** apply the `.sql` files in this folder one-by-one
  anymore. They are documentation of how each change was originally
  introduced.

## Files in this folder

| File                                       | Status                                                    |
| ------------------------------------------ | --------------------------------------------------------- |
| `add_application_form_data.sql`            | folded into schema.sql (M01)                              |
| `add_category_to_interview_questions.sql`  | folded into schema.sql (M02)                              |
| `add_custom_application_questions.sql`     | folded into schema.sql (M03)                              |
| `add_in_progress_status.sql`               | folded into schema.sql (M04, guarded)                     |
| `add_job_interview_settings.sql`           | folded into schema.sql (M05)                              |
| `add_kanban_stages.sql`                    | folded into schema.sql (M06)                              |
| `add_resume_job_scores.sql`                | folded into schema.sql (M07, guarded DROP DEFAULT)        |
| `update_application_status.sql`            | superseded by M06 (NOT NULL guard); kept for history      |
| `update_sentiment_to_text.sql`             | folded into schema.sql (M09, guarded)                     |
| `backfill_kanban_stages.sql`               | folded into schema.sql (M10, idempotent data backfill)    |
| `backfill_kanban_stages.py`                | one-shot Python equivalent of the .sql backfill           |

## Adding a new schema change

1. Add the change directly to `database/schema.sql`:
   - Update the original `CREATE TABLE` if you're adding a brand-new column to a fresh-DB definition.
   - **Also** append an idempotent guard (`ADD COLUMN IF NOT EXISTS`, `DO $$ ... $$`) in the FOLDED MIGRATIONS section at the bottom so existing databases pick it up on re-run.
2. Optionally drop a copy of the standalone migration `.sql` here for archival, but it is not required.
3. Verify locally by running `psql -f database/schema.sql` twice against the same database — the second run must complete without errors.
