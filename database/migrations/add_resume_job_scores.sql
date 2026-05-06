BEGIN;

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

ALTER TABLE applications ALTER COLUMN ai_match_score DROP DEFAULT;

COMMIT;
