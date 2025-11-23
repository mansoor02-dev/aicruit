-- Enable UUID Extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================
-- USERS TABLE
-- ============================
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR(150) NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('candidate','recruiter','admin')),
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- CANDIDATES TABLE
-- ============================
CREATE TABLE IF NOT EXISTS candidates (
    id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    phone VARCHAR(50),
    profile_completed BOOLEAN DEFAULT FALSE
);

-- ============================
-- RESUMES TABLE
-- ============================
CREATE TABLE IF NOT EXISTS resumes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    original_file_url TEXT NOT NULL,
    parsed_json JSONB NOT NULL,
    parse_status VARCHAR(20) DEFAULT 'success',
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- JOBS TABLE
-- ============================
CREATE TABLE IF NOT EXISTS jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    recruiter_id UUID REFERENCES users(id) ON DELETE SET NULL,
    title VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    requirements TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- INTERVIEWS TABLE
-- ============================
CREATE TABLE IF NOT EXISTS interviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
    job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
    scheduled_at TIMESTAMP NOT NULL,
    status VARCHAR(20) DEFAULT 'scheduled'
        CHECK (status IN ('scheduled','completed','cancelled','expired')),
    cheating_risk_score INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- INTERVIEW QUESTIONS
-- ============================
CREATE TABLE IF NOT EXISTS interview_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    question_number INT NOT NULL,
    question_text TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- INTERVIEW RESPONSES
-- ============================
CREATE TABLE IF NOT EXISTS interview_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    question_id UUID REFERENCES interview_questions(id) ON DELETE CASCADE,
    audio_url TEXT,
    video_url TEXT,
    transcript TEXT,
    ai_score INT,
    confidence_score INT,
    communication_score INT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- CHEATING EVENTS
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
-- SCORE OVERRIDES
-- ============================
CREATE TABLE IF NOT EXISTS score_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    response_id UUID REFERENCES interview_responses(id) ON DELETE CASCADE,
    recruiter_id UUID REFERENCES users(id),
    old_score INT,
    new_score INT,
    reason TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- REPORTS
-- ============================
CREATE TABLE IF NOT EXISTS reports (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    interview_id UUID REFERENCES interviews(id) ON DELETE CASCADE,
    technical_fit_score INT,
    communication_score INT,
    cheating_risk_score INT,
    summary TEXT,
    explainability_json JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- AUDIT LOGS
-- ============================
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    action VARCHAR(200),
    ip_address VARCHAR(100),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- SYSTEM LOGS
-- ============================
CREATE TABLE IF NOT EXISTS system_logs (
    id BIGSERIAL PRIMARY KEY,
    level VARCHAR(20),
    message TEXT,
    service VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

-- ============================
-- UPLOAD FILE
-- ===========================

CREATE TABLE IF NOT EXISTS file_uploads (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    file_type VARCHAR(50) NOT NULL,   -- resume, profile_picture, generic
    file_url TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    mime_type VARCHAR(100),
    size BIGINT,
    created_at TIMESTAMP DEFAULT NOW()
);
