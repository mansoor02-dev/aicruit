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

ALTER TABLE applications ADD COLUMN IF NOT EXISTS stage_id UUID
  REFERENCES job_stages(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_applications_job_stage ON applications(job_id, stage_id);

ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_status_check;
ALTER TABLE applications ADD CONSTRAINT applications_status_not_null CHECK (status IS NOT NULL);

ALTER TABLE interviews ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';
