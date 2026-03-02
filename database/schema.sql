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
    technical_fit_score INT,
    communication_score INT,
    cheating_risk_score INT,
    summary TEXT,
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