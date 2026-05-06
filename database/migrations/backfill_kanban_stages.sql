-- Idempotent backfill for kanban stages.
--
-- Mirrors database/migrations/backfill_kanban_stages.py:
--   1. Seed default job_stages rows for any job that has none, choosing
--      stage names based on job_interview_settings.ai_interview_enabled.
--   2. Backfill applications.stage_id for every row where stage_id IS NULL
--      and status != 'REJECTED', mapping legacy status -> stage by position.
--
-- Re-running is safe: the seed step only inserts when the job has zero
-- stages, and the backfill step only updates rows where stage_id IS NULL.
--
-- Usage:
--   cat database/migrations/backfill_kanban_stages.sql \
--     | docker exec -i docker-postgres-1 psql -U admin -d aicruit

BEGIN;

-- ---------------------------------------------------------------------------
-- Step 1: Seed default stages for jobs with zero job_stages rows.
-- ---------------------------------------------------------------------------
WITH jobs_needing_stages AS (
    SELECT j.id AS job_id,
           COALESCE(jis.ai_interview_enabled, FALSE) AS ai_enabled
    FROM jobs j
    LEFT JOIN job_interview_settings jis ON jis.job_id = j.id
    WHERE NOT EXISTS (
        SELECT 1 FROM job_stages s WHERE s.job_id = j.id
    )
),
default_stages AS (
    -- AI off: two stages
    SELECT job_id, position, name
    FROM jobs_needing_stages
    CROSS JOIN LATERAL (
        VALUES (0, 'Applied'), (1, 'Shortlisted')
    ) AS v(position, name)
    WHERE ai_enabled = FALSE

    UNION ALL

    -- AI on: three stages
    SELECT job_id, position, name
    FROM jobs_needing_stages
    CROSS JOIN LATERAL (
        VALUES (0, 'Applied'), (1, 'AI Interview'), (2, 'Shortlisted')
    ) AS v(position, name)
    WHERE ai_enabled = TRUE
)
INSERT INTO job_stages (job_id, position, name)
SELECT job_id, position, name
FROM default_stages
ON CONFLICT (job_id, position) DO NOTHING;

-- ---------------------------------------------------------------------------
-- Step 2: Backfill applications.stage_id from legacy status.
--
-- Mapping:
--   APPLIED, SCREENING                           -> position 0 (first)
--   INTERVIEW_SCHEDULED, INTERVIEW_COMPLETED     -> position 1 if AI on,
--                                                   else last position
--   OFFERED                                      -> last position (max)
--   REJECTED                                     -> leave NULL
--   anything else                                -> leave NULL (no-op)
-- ---------------------------------------------------------------------------
WITH job_stage_meta AS (
    SELECT job_id,
           MAX(position) AS max_position
    FROM job_stages
    GROUP BY job_id
),
target AS (
    SELECT a.id AS application_id,
           CASE
               WHEN UPPER(a.status) IN ('APPLIED', 'SCREENING') THEN 0
               WHEN UPPER(a.status) IN ('INTERVIEW_SCHEDULED', 'INTERVIEW_COMPLETED') THEN
                    CASE
                        WHEN COALESCE(jis.ai_interview_enabled, FALSE) = TRUE
                             AND jsm.max_position >= 2
                        THEN 1
                        ELSE jsm.max_position
                    END
               WHEN UPPER(a.status) = 'OFFERED' THEN jsm.max_position
               ELSE NULL
           END AS target_position,
           a.job_id
    FROM applications a
    LEFT JOIN job_interview_settings jis ON jis.job_id = a.job_id
    LEFT JOIN job_stage_meta jsm ON jsm.job_id = a.job_id
    WHERE a.stage_id IS NULL
      AND UPPER(COALESCE(a.status, '')) <> 'REJECTED'
)
UPDATE applications a
SET stage_id = js.id
FROM target t
JOIN job_stages js
  ON js.job_id = t.job_id
 AND js.position = t.target_position
WHERE a.id = t.application_id
  AND a.stage_id IS NULL
  AND t.target_position IS NOT NULL;

-- ---------------------------------------------------------------------------
-- Step 3: Report counts.
-- ---------------------------------------------------------------------------
DO $$
DECLARE
    total_jobs INTEGER;
    jobs_without_stages INTEGER;
    apps_without_stage INTEGER;
    apps_rejected_null INTEGER;
BEGIN
    SELECT COUNT(*) INTO total_jobs FROM jobs;
    SELECT COUNT(*) INTO jobs_without_stages
      FROM jobs j
      WHERE NOT EXISTS (SELECT 1 FROM job_stages s WHERE s.job_id = j.id);
    SELECT COUNT(*) INTO apps_without_stage
      FROM applications
      WHERE stage_id IS NULL
        AND UPPER(COALESCE(status, '')) <> 'REJECTED';
    SELECT COUNT(*) INTO apps_rejected_null
      FROM applications
      WHERE stage_id IS NULL
        AND UPPER(COALESCE(status, '')) = 'REJECTED';

    RAISE NOTICE '[backfill] total jobs: %', total_jobs;
    RAISE NOTICE '[backfill] jobs still without stages (should be 0): %', jobs_without_stages;
    RAISE NOTICE '[backfill] non-rejected applications still without stage_id (should be 0 unless status is unknown): %', apps_without_stage;
    RAISE NOTICE '[backfill] rejected applications with NULL stage_id (expected, rejected lane): %', apps_rejected_null;
END $$;

COMMIT;
