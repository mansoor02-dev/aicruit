# AI Resume-Fit Score — Design Spec

**Status:** Approved (brainstorm complete)
**Date:** 2026-05-01
**Branch:** `job-application-improvments`
**Depends on:** `2026-05-01-recruiter-kanban-stages-design.md` (uses the existing apply flow + `applications.ai_match_score` column).

## 1. Goal

When a candidate uploads a resume during a job application, compute an LLM-based fit score (0–100) of the resume against that specific job description. Persist the final score on the `applications` row at submit time, keyed by the resume the candidate ultimately chose. The score is stored for future use on the recruiter dashboard; it is NOT exposed in any current API response.

## 2. Scope

In scope:
- New scoring endpoint on the `resume-parser` service: `POST /score-fit`.
- New table `resume_job_scores` keyed by `(resume_id, job_id)` storing the overall integer.
- Modify the gateway's `POST /upload-resume` to call `/score-fit` when a `job_id` is provided, and upsert the score row.
- Modify the gateway's `POST /apply` to copy the score for the chosen `(resume_id, job_id)` into `applications.ai_match_score`.
- Frontend apply modal passes `job_id` on resume upload (no UI change).

Out of scope:
- Displaying the score anywhere in the UI (deliberate; reserved for a future recruiter-dashboard ranking feature).
- Historical backfill of scores for applications already in the DB.
- Re-scoring on every job-description edit; the score reflects the JD as it was at upload time.
- Caching across `(candidate, job)` — each upload generates a new `resume_id` and triggers a fresh score.

## 3. User-facing behavior

The candidate sees no change. The apply modal still uploads the resume, parses it, and shows the autofill form. Internally:

1. Upload + parse runs as today.
2. Immediately after parsing succeeds, the gateway calls the new `/score-fit` endpoint with the parsed resume + the job's key fields.
3. The integer overall score is upserted into `resume_job_scores`.
4. Total perceived latency: parse + score (~5–8s on Gemini Flash; the modal's existing "Analyzing your resume..." spinner covers both).
5. On apply submit, the gateway looks up the score for the chosen `(resume_id, job_id)` and writes it to `applications.ai_match_score`. If no score exists (LLM was down at upload time), `ai_match_score` is left NULL.

The score does not appear in any GET response. Recruiter views are unchanged.

## 4. Data model

### 4.1 New table: `resume_job_scores`
```sql
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
```

Sub-scores (`skills_match`, `experience_match`, `education_match`, `project_match`) and the `rationale` are NOT persisted. They flow through Python memory in the gateway, get logged at INFO level for debugging, and are dropped.

### 4.2 `applications.ai_match_score`
- Column already exists (`Column(Integer, default=0)` in `application_model.py`).
- Migration: drop the default. Recommended state is **nullable with no default** so NULL means "not scored."
  ```sql
  ALTER TABLE applications ALTER COLUMN ai_match_score DROP DEFAULT;
  ```
- Existing rows with `ai_match_score = 0` are left as-is (treated as "scored 0" — recruiters can ignore the data point if it ever surfaces).

### 4.3 New SQLAlchemy model
File: `gateway/app/models/resume_job_score_model.py`
```python
import uuid
from sqlalchemy import Column, Integer, DateTime, ForeignKey, UniqueConstraint, CheckConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from ..core.db import Base

class ResumeJobScoreModel(Base):
    __tablename__ = "resume_job_scores"
    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    resume_id   = Column(UUID(as_uuid=True), ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False)
    job_id      = Column(UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False)
    overall     = Column(Integer, nullable=False)
    created_at  = Column(DateTime(timezone=True), default=func.now())
    updated_at  = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    __table_args__ = (
        UniqueConstraint("resume_id", "job_id", name="uq_resume_job_score"),
        CheckConstraint("overall BETWEEN 0 AND 100", name="ck_resume_job_score_range"),
    )
```

## 5. LLM scoring (resume-parser service)

### 5.1 New endpoint: `POST /score-fit`
Lives in `services/resume-parser/app/api.py`.

Request body:
```python
class ScoreFitRequest(BaseModel):
    resume: dict   # parsed resume JSON: personal_info, skills, experience, education, projects, ...
    job: dict      # title, description, required_skills, experience_level, location, type
```

Response body:
```python
class ScoreFitResponse(BaseModel):
    overall: int
    skills_match: int
    experience_match: int
    education_match: int
    project_match: int
    rationale: str
```

### 5.2 System prompt (frozen)

```
You are a hiring assistant evaluating how well a candidate's resume matches a job posting.

You will be given:
1. A job description (title, description, required_skills, experience_level, location, type).
2. A parsed resume (skills, experience entries with title/company/duration, education, projects).

Score the candidate on a 0-100 scale across four dimensions:

- skills_match (0-100): How well the candidate's listed skills cover the job's required_skills.
  Required skills are MUST-HAVE. Missing all of them caps this dimension at 20.
  Adjacent/transferable skills (e.g., "TypeScript" for a "JavaScript" requirement) count as partial credit.
- experience_match (0-100): Does the candidate's work history align with the role's seniority and domain?
  Treat experience_level as a soft signal — note mismatches in rationale but do not hard-cap.
  Weight relevance over years (3 yrs of directly-relevant beats 8 yrs of unrelated).
- education_match (0-100): Does education align? For most roles, default this to 70+ unless the JD
  explicitly demands a specific degree the candidate lacks.
- project_match (0-100): Do listed projects demonstrate the kinds of work this role involves?
  If no projects listed and the JD doesn't emphasize them, default to 60.

Then compute overall (0-100) as a weighted average:
  overall = round(0.45 * skills_match + 0.30 * experience_match + 0.10 * education_match + 0.15 * project_match)

Return ONLY valid JSON in this exact shape:
{
  "skills_match": int,
  "experience_match": int,
  "education_match": int,
  "project_match": int,
  "overall": int,
  "rationale": "1-3 sentences explaining the overall score, focused on the strongest match factors and the most significant gaps."
}

Rules:
- Be calibrated, not generous. A truly average match is 50, not 75.
- Never exceed 100 or go below 0 on any dimension.
- Do not invent skills/experience the resume doesn't list.
- If the resume is essentially empty, return all zeros and rationale "Resume contains insufficient information to evaluate."
```

### 5.3 LLM call
- Model: Gemini 2.5 Flash (same as the existing parser).
- `response_mime_type: "application/json"`.
- Timeout: 15 seconds.
- Implementation: add `_run_gemini_for_score(system_prompt: str, user_payload: str) -> dict` to `services/resume-parser/app/inference.py` (or generalize the existing `_run_gemini` to accept a system prompt — either is fine, prefer the smaller diff).
- Server-side validation: clamp each int to [0, 100]; if response shape is malformed, raise 502.

### 5.4 Failure semantics
- Gemini error / timeout / malformed JSON → 502 `{"detail": "scoring_unavailable"}`.
- Gateway treats 502 as "no score" → no row written → `application.ai_match_score = NULL` at submit time.

## 6. Gateway changes

### 6.1 `POST /upload-resume` (`gateway/app/routes/job.py`)
- Accept an optional `job_id: UUID | None = None` (Form field if multipart; query param otherwise — match the existing handler's parameter style).
- After parsing succeeds (existing flow), if `job_id` is provided:
  1. Look up the job. 404 if not found, 403 if not OPEN.
  2. Build a small `job_payload` dict: `{title, description, required_skills, experience_level, location, type}`.
  3. Build `resume_payload`: the parsed JSON returned by the resume-parser (the same dict the gateway already has in scope).
  4. Call `resume_scoring.score_resume_for_job(resume_payload, job_payload)`.
  5. If returned int → upsert `(resume_id=resume.id, job_id=job_id, overall=score)` with `ON CONFLICT (resume_id, job_id) DO UPDATE`.
  6. If returned None → log warning, no row written.
- Response shape unchanged.
- If `job_id` is missing (profile-page upload) → skip steps 1–6.

### 6.2 New gateway service: `gateway/app/services/resume_scoring.py`
```python
async def score_resume_for_job(resume: dict, job: dict) -> Optional[int]:
    """Call the resume-parser /score-fit endpoint. Return overall (int) or None on failure."""
    url = f"{RESUME_PARSER_URL}/score-fit"
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            r = await client.post(url, json={"resume": resume, "job": job})
            r.raise_for_status()
            data = r.json()
            overall = max(0, min(100, int(data["overall"])))
            logger.info("resume_scoring.success", extra={"overall": overall, "sub": {k: data.get(k) for k in ('skills_match','experience_match','education_match','project_match')}, "rationale": data.get("rationale")})
            return overall
    except (httpx.HTTPError, ValueError, KeyError) as e:
        logger.warning("resume_scoring.failed", extra={"error": str(e)})
        return None
```

### 6.3 `POST /apply` (`gateway/app/routes/job.py`)
- Right before constructing `ApplicationModel(...)`:
  ```python
  score_row = (
      db.query(ResumeJobScoreModel)
      .filter_by(resume_id=resume.id, job_id=application_data.job_id)
      .first()
  )
  ai_match_score = score_row.overall if score_row else None
  ```
- Pass `ai_match_score=ai_match_score` in the constructor.
- The temp `resume_job_scores` row is NOT deleted on apply. Kept for debugging and for the future case where the candidate re-applies (same row gets reused).

## 7. Frontend changes

### 7.1 `frontend/src/components/ApplyJobModal.tsx`
- Locate the existing upload call (the `fetch` / `apiRequest` to `/job/upload-resume`).
- Append the job's id to the request: either as a query string (`/job/upload-resume?job_id=<id>`) or as a FormData field — match whatever shape the backend handler expects after Section 6.1's change.
- No other UI changes. The "Analyzing your resume..." spinner already covers the extra LLM latency.

## 8. Edge cases

- **Resume parse fails entirely** → `parsed_resume` is the empty fallback. Gateway still calls `/score-fit`; the LLM returns `overall: 0` per the prompt rule. Row is written with 0.
- **`required_skills` is empty on the job** → LLM has nothing to anchor `skills_match`; per prompt, "Adjacent/transferable" still applies. Score will trend toward `experience_match` weight.
- **Candidate uploads N resumes during one apply session** → N rows in `resume_job_scores` (one per resume_id). Final apply uses whichever resume_id is in the submit body.
- **Candidate uploads same resume_id twice for the same job** (theoretically impossible since each upload mints a new resume_id, but guarded by `UNIQUE`) → upsert overwrites the previous score.
- **Candidate uploads a resume on the profile page** → `job_id` not passed → no scoring. Existing behavior preserved.
- **Recruiter edits the JD after a candidate uploaded a scored resume but before they applied** → score reflects the JD at upload time, not at apply time. Acceptable; out-of-scope concern.
- **Two candidates upload concurrently** → independent rows, no contention. The upsert is per `(resume_id, job_id)`; resume_ids are per-candidate.
- **LLM returns `overall = 105`** → clamped to 100 by `score_resume_for_job` before return.
- **`/score-fit` returns malformed JSON** → 502 → gateway returns None → no row → NULL at apply.
- **Job is CLOSED at upload time** → 403 from the gateway's job lookup → no scoring (consistent with rejecting the apply itself).

## 9. Migration

`database/migrations/add_resume_job_scores.sql`:
```sql
BEGIN;

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

ALTER TABLE applications ALTER COLUMN ai_match_score DROP DEFAULT;

COMMIT;
```

Per CLAUDE.md, applied manually.

## 10. Testing

- **resume-parser unit test (`services/resume-parser/tests/test_score_fit.py`)**:
  - Mock the Gemini call. Assert: clamps over-100 to 100, clamps below-0 to 0, raises 502 on malformed JSON, returns the validated dict on a well-shaped response.
- **gateway unit test (`gateway/tests/test_resume_scoring.py`)**:
  - Mock the resume-parser HTTP call. Assert: `score_resume_for_job` returns int on success, returns None on httpx error / non-int / missing key.
- **gateway integration test (`gateway/tests/test_apply_with_score.py`)**:
  - Seed a job + a resume + a `resume_job_scores` row with overall=72. POST `/apply`. Assert: created `applications.ai_match_score == 72`.
  - Same but no score row → assert `ai_match_score IS NULL`.
- **Manual smoke**: docker compose up, log in as candidate, apply to a job, check Postgres: `SELECT overall FROM resume_job_scores WHERE resume_id = ...` and `SELECT ai_match_score FROM applications WHERE id = ...`.

## 11. Rollout

Single PR on the existing `job-application-improvments` branch:
1. Apply SQL migration.
2. Resume-parser: add `/score-fit` endpoint + Gemini wrapper.
3. Gateway: new `ResumeJobScoreModel`, new `resume_scoring` service, modify `/upload-resume`, modify `/apply`.
4. Frontend: pass `job_id` on resume upload.
5. Restart gateway + resume-parser containers.

## 12. Open / deferred

- Recruiter-dashboard ranking/sort by `ai_match_score` — separate spec.
- Re-score on JD edit — explicitly deferred.
- Caching across applications by `(candidate, job)` — not needed since `resume_id` changes per upload.
- Persisting sub-scores and rationale — deferred until a "show breakdown" UI exists.
- Backfill of scores for pre-existing applications — deferred until a need arises.
