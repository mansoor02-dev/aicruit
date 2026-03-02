-- Update sentiment column from VARCHAR(20) to TEXT in interview_responses table
ALTER TABLE interview_responses 
ALTER COLUMN sentiment TYPE TEXT;
