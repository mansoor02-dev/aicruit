 -- Add category column to interview_questions table
-- This tracks which skill/topic each question belongs to (NULL = intro question)
ALTER TABLE interview_questions ADD COLUMN IF NOT EXISTS category VARCHAR(100);
 