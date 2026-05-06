-- =============================================================================
-- AIcruit database schema
--
-- This file is self-contained and idempotent. For a fresh DB, run it directly.
-- For an existing DB, re-running it safely applies any missing changes.
-- The files in ./migrations/ are folded into this file and kept for history only.
-- =============================================================================

-- Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================
-- 1. COMPANIES (New: SaaS Parent)
-- ============================
CREATE TABLE IF NOT EXISTS companies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    logo_url TEXT,
    website VARCHAR(255),
    -- Simple billing fields for future use
    subscription_status VARCHAR(50) DEFAULT 'ACTIVE', 
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- 2. USERS (Auth Base) 
-- ============================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    -- password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('CANDIDATE','RECRUITER','ADMIN')),
    cognito_sub VARCHAR(100) UNIQUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- 3. RECRUITERS (New: Links User to Company)
-- ============================
CREATE TABLE IF NOT EXISTS recruiters (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE,
    is_admin BOOLEAN DEFAULT FALSE
);

-- ============================
-- 4. CANDIDATES (Specific Profile)
-- ============================
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    phone VARCHAR(50),
    linkedin_url TEXT,
    bio TEXT,
    profile_completed BOOLEAN DEFAULT FALSE
);

-- ============================
-- 5. JOBS (Updated with AI fields)
-- ============================
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id UUID REFERENCES companies(id) ON DELETE CASCADE, -- Link to Company
    recruiter_id UUID REFERENCES recruiters(id) ON DELETE SET NULL, -- Who posted it
    
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    location VARCHAR(100),
    type VARCHAR(50), -- Remote, Onsite, Hybrid
    
    -- AI Matching Fields
    required_skills JSONB DEFAULT '[]', -- e.g. ["Flutter", "Python"]
    experience_level VARCHAR(50),       -- e.g. "Senior"
    
    -- Logistics
    salary_min INT,
    salary_max INT,
    status VARCHAR(20) DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED','DRAFT')),
    last_date_to_apply TIMESTAMP,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- 6. RESUMES (Fixed Relation)
-- ============================
CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    file_url TEXT NOT NULL,
    parsed_text TEXT,           -- Raw text extracted by AI
    parsed_skills JSONB,        -- AI extracted skills ["Java", "SQL"]
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- 7. APPLICATIONS (New: The ATS Logic)
-- ============================
-- This tracks the candidate's progress for a specific job
CREATE TABLE IF NOT EXISTS applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    resume_id UUID REFERENCES resumes(id),
    
    -- Candidate-submitted form data
    applicant_name VARCHAR(255),
    applicant_email VARCHAR(255),
    applicant_phone VARCHAR(100),
    applicant_location VARCHAR(255),
    summary TEXT,
    skills JSONB DEFAULT '[]',
    education JSONB DEFAULT '[]',
    experience JSONB DEFAULT '[]',
    projects JSONB DEFAULT '[]',
    
    -- Status Pipeline
    status VARCHAR(50) DEFAULT 'APPLIED' 
        CHECK (status IN ('APPLIED', 'SCREENING', 'INTERVIEW_SCHEDULED', 'INTERVIEW_COMPLETED', 'OFFERED', 'REJECTED')),
    
    -- AI Scoring (Populate this via your /ai/parse endpoint)
    ai_match_score INT DEFAULT 0, 
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    UNIQUE(job_id, candidate_id) -- Prevent double applying
);

-- ============================
-- 8. INTERVIEWS (Linked to Application)
-- ============================
CREATE TABLE IF NOT EXISTS interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    application_id UUID REFERENCES applications(id) ON DELETE CASCADE, -- Link to specific application
    
    scheduled_at TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled'
        CHECK (status IN ('scheduled','in_progress','completed','cancelled','expired')),
    
    cheating_risk_score INT DEFAULT 0,
    next_snapshot_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ========= ===================
-- 9. INTERVIEW QUESTIONS
-- ============================
CREATE TABLE IF NOT EXISTS interview_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    question_text TEXT NOT NULL,
    question_order INT, -- To keep sequence 1, 2, 3
    category VARCHAR(100), -- Skill/topic category (NULL = intro)
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- 10. INTERVIEW RESPONSES (AI Analysis)
-- ============================
CREATE TABLE IF NOT EXISTS interview_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    question_id UUID REFERENCES interview_questions(id) ON DELETE CASCADE,
    
    video_url TEXT,
    audio_url TEXT,
    transcript TEXT,
    
    -- AI Grading
    ai_score INT,
    confidence_score INT,
    communication_score INT,
    sentiment TEXT,
    
    created_at TIMESTAMP DEFAULT NOW()
);


-- ============================
-- INTERVIEW Turns
-- ============================
-- Add to your existing schema.sql (or run separately)

-- Link between your old interviews and our AI session
CREATE TABLE IF NOT EXISTS ai_interview_sessions (
    id SERIAL PRIMARY KEY,
    interview_id UUID NOT NULL REFERENCES interviews(id) ON DELETE CASCADE,
    session_id TEXT UNIQUE NOT NULL,           -- our short 8-char session ID
    resume_id UUID NOT NULL,                   -- from resumes table
    job_description TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT NOW(),
    ended_at TIMESTAMP
);

-- Store every question + answer
CREATE TABLE IF NOT EXISTS ai_interview_turns (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES ai_interview_sessions(session_id) ON DELETE CASCADE,
    turn_number INT NOT NULL,
    question TEXT NOT NULL,
    user_answer TEXT,
    is_followup BOOLEAN DEFAULT FALSE,
    topic TEXT,
    depth_score NUMERIC(4,3),
    pass BOOLEAN,
    confidence NUMERIC(4,3),
    feedback TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- 11. CHEATING EVENTS
-- ============================
CREATE TABLE IF NOT EXISTS cheating_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    event_type VARCHAR(50)
        CHECK(event_type IN ('multiple_faces','no_face','gaze_offscreen','audio_video_mismatch')),
    timestamp_seconds INT,
    frame_url TEXT,
    severity INT DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- 12. REPORTS & LOGS
-- ============================
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    overall_score NUMERIC(5,2),
    category_scores JSONB,
    overall_remark TEXT,
    strengths JSONB,
    improvements JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Generic Uploads
CREATE TABLE IF NOT EXISTS file_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    file_type VARCHAR(50), 
    file_url TEXT NOT NULL,
    original_filename TEXT,
    mime_type VARCHAR(100),
    size BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);
-- ============================
-- 13. JOB INTERVIEW SETTINGS
-- ============================
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

-- ============================
-- 14. SNAPSHOTS (Proctoring)
-- ============================
CREATE TABLE IF NOT EXISTS snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    camera_url TEXT,
    screen_url TEXT,
    client_timestamp BIGINT,
    server_timestamp BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);


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
