-- Migration: Custom application questions for jobs + candidate responses
-- ----------------------------------------------------------------------
-- Recruiters can attach a list of custom questions to a job (e.g.
-- "Why do you want to join XYZ?", "Years of React experience"). Each
-- question carries its own response-type spec (text/number/date/select/
-- yes_no/email/url) plus per-type validation (min/max length, min/max
-- value, options) and a `required` flag.
--
-- Candidates' answers are stored as a JSONB array on the application,
-- keyed by question_id so we can render answers next to the original
-- question label even after the recruiter edits the question list.

ALTER TABLE jobs
    ADD COLUMN IF NOT EXISTS application_questions JSONB DEFAULT '[]';

ALTER TABLE applications
    ADD COLUMN IF NOT EXISTS question_responses JSONB DEFAULT '[]';

-- Shape stored in jobs.application_questions:
-- [
--   {
--     "id": "q_1",                 -- stable client-generated id
--     "label": "Why XYZ?",         -- shown to candidate
--     "help_text": "...optional",
--     "type": "text",              -- text | textarea | number | date | select | yes_no | email | url
--     "required": true,
--     "min_length": 50,            -- text/textarea only
--     "max_length": 500,           -- text/textarea only
--     "min_value": 0,              -- number only
--     "max_value": 100,            -- number only
--     "options": ["A", "B"]        -- select only
--   }, ...
-- ]
--
-- Shape stored in applications.question_responses:
-- [
--   { "question_id": "q_1", "label": "Why XYZ?", "type": "text", "value": "..." }, ...
-- ]
