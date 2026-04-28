-- Migration: Add candidate form data columns to applications table
-- Run this against an existing database to add the new columns

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
