header = """-- =============================================================================
-- AIcruit database schema
--
-- This file is self-contained and idempotent. For a fresh DB, run it directly.
-- For an existing DB, re-running it safely applies any missing changes.
-- The files in ./migrations/ are folded into this file and kept for history only.
-- =============================================================================

"""

with open("database/schema.sql", "r", encoding="utf-8") as f:
    original = f.read()

migrations_section = r"""

-- =============================================================================
-- FOLDED MIGRATIONS (applied idempotently below)
-- =============================================================================

-- M01: add_application_form_data.sql
ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS applicant_name VARCHAR(255),
    ADD COLUMN IF NOT EXISTS applicant_email VARCHAR(255),
    ADD COLUMN IF NOT EXISTS applicant_phone VARCHAR(100),
    ADD COLUMN IF NOT EXISTS applicant_location VARCHAR(255),
    ADD COLUMN IF NOT EXISTS summary TEXT,
    ADD COLUMN IF NOT EXISTS skills JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS education JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS experience JSONB DEFAULT '[]',
    ADD COLUMN IF NOT EXISTS projects JSONB DEFAULT '[]';

-- M02: add_category_to_interview_questions.sql
ALTER TABLE interview_questions
    ADD COLUMN IF NOT EXISTS category VARCHAR(100);

-- M03: add_custom_application_questions.sql
ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS application_questions JSONB DEFAULT '[]';
ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS question_responses JSONB DEFAULT '[]';

-- M04: add_in_progress_status.sql
DO $mig04$
DECLARE
    cdef TEXT;
BEGIN
    SELECT pg_get_constraintdef(oid) INTO cdef
      FROM pg_constraint
     WHERE conname = 'interviews_status_check';
    IF cdef IS NULL OR cdef NOT LIKE '%in_progress%' THEN
        ALTER TABLE interviews DROP CONSTRAINT IF EXISTS interviews_status_check;
        ALTER TABLE interviews ADD CONSTRAINT interviews_status_check
            CHECK (status IN ('scheduled','in_progress','completed','cancelled','expired'));
    END IF;
END
$mig04$;

-- M05: add_job_interview_settings.sql (table created above; ensure index)
CREATE INDEX IF NOT EXISTS idx_job_interview_settings_job_id
    ON job_interview_settings(job_id);

-- M06: add_kanban_stages.sql
CREATE TABLE IF NOT EXISTS job_stages (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    position    INT  NOT NULL,
    name        VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (job_id, position)
);
CREATE INDEX IF NOT EXISTS idx_job_stages_job ON job_stages(job_id);

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS stage_id UUID REFERENCES job_stages(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_applications_job_stage
    ON applications(job_id, stage_id);

DO $mig06a$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'applications_status_not_null'
    ) THEN
        ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_status_check;
        ALTER TABLE applications ADD CONSTRAINT applications_status_not_null
            CHECK (status IS NOT NULL);
    END IF;
END
$mig06a$;

ALTER TABLE interviews
    ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';

-- M07: add_resume_job_scores.sql
CREATE TABLE IF NOT EXISTS resume_job_scores (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    resume_id   UUID NOT NULL REFERENCES resumes(id) ON DELETE CASCADE,
    job_id      UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    overall     INT  NOT NULL CHECK (overall BETWEEN 0 AND 100),
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now(),
    UNIQUE (resume_id, job_id)
);
CREATE INDEX IF NOT EXISTS idx_resume_job_scores_resume_job
    ON resume_job_scores(resume_id, job_id);

DO $mig07$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'applications'
           AND column_name = 'ai_match_score'
           AND column_default IS NOT NULL
    ) THEN
        ALTER TABLE applications ALTER COLUMN ai_match_score DROP DEFAULT;
    END IF;
END
$mig07$;

-- M08: update_application_status.sql -- superseded by M06 (NOT NULL guard); no-op.

-- M09: update_sentiment_to_text.sql
DO $mig09$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'interview_responses'
           AND column_name = 'sentiment'
           AND data_type <> 'text'
    ) THEN
        ALTER TABLE interview_responses ALTER COLUMN sentiment TYPE TEXT;
    END IF;
END
$mig09$;

-- M10: backfill_kanban_stages.sql (idempotent data backfill)
WITH jobs_needing_stages AS (
    SELECT j.id AS job_id,
           COALESCE(jis.ai_interview_enabled, FALSE) AS ai_enabled
      FROM jobs j
      LEFT JOIN job_interview_settings jis ON jis.job_id = j.id
     WHERE NOT EXISTS (SELECT 1 FROM job_stages s WHERE s.job_id = j.id)
),
default_stages AS (
    SELECT job_id, position, name
      FROM jobs_needing_stages
      CROSS JOIN LATERAL (VALUES (0, 'Applied'), (1, 'Shortlisted')) AS v(position, name)
     WHERE ai_enabled = FALSE
    UNION ALL
    SELECT job_id, position, name
      FROM jobs_needing_stages
      CROSS JOIN LATERAL (VALUES (0, 'Applied'), (1, 'AI Interview'), (2, 'Shortlisted')) AS v(position, name)
     WHERE ai_enabled = TRUE
)
INSERT INTO job_stages (job_id, position, name)
SELECT job_id, position, name FROM default_stages
ON CONFLICT (job_id, position) DO NOTHING;

WITH job_stage_meta AS (
    SELECT job_id, MAX(position) AS max_position
      FROM job_stages GROUP BY job_id
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
"""

new_content = header + original.lstrip() + migrations_section

with open("database/schema.sql", "w", encoding="utf-8", newline="\n") as f:
    f.write(new_content)

print(f"Wrote {len(new_content)} bytes")
