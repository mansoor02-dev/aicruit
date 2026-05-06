-- Per-job interview settings
CREATE TABLE IF NOT EXISTS job_interview_settings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL UNIQUE REFERENCES jobs(id) ON DELETE CASCADE,
    ai_interview_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    uploaded_questions JSONB,
    topics JSONB NOT NULL DEFAULT '[]'::jsonb,
    fixed_question_count BOOLEAN NOT NULL DEFAULT FALSE,
    number_of_questions INT,
    max_questions INT,
    difficulty_level TEXT,
    interview_stages INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    CONSTRAINT job_interview_settings_difficulty_chk
        CHECK (difficulty_level IS NULL OR difficulty_level IN ('low','medium','high','very_high','varying'))
);

CREATE INDEX IF NOT EXISTS idx_job_interview_settings_job_id ON job_interview_settings(job_id);
