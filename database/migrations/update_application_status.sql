-- Drop the old constraint
ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_status_check;

-- Add the new constraint with INTERVIEW_COMPLETED
ALTER TABLE applications ADD CONSTRAINT applications_status_check 
CHECK (status IN ('APPLIED', 'SCREENING', 'INTERVIEW_SCHEDULED', 'INTERVIEW_COMPLETED', 'OFFERED', 'REJECTED'));
