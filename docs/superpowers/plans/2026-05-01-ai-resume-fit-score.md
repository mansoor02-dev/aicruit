# AI Resume-Fit Score Implementation Plan

> **For agentic workers:** Wave-based plan for parallel execution. Slices within a wave are independent. Reference the spec at `docs/superpowers/specs/2026-05-01-ai-resume-fit-score-design.md` for full requirements.

**Goal:** Compute and persist an LLM-based fit score (0–100) for each candidate resume against the specific job they apply to. Score is stored, not displayed.

**Architecture:** New `/score-fit` endpoint on the resume-parser service (Gemini 2.5 Flash). New `resume_job_scores` table keyed by `(resume_id, job_id)`. Gateway calls `/score-fit` during `POST /upload-resume` when a `job_id` is supplied; copies the resulting overall to `applications.ai_match_score` at apply time.

**Tech Stack:** FastAPI + SQLAlchemy + Gemini 2.5 Flash (Google GenAI SDK) + Next.js 14.

---

## Wave 1 — Foundation (parallel)

### Slice A — DB migration + SQLAlchemy model
**Files**
- Create: `database/migrations/add_resume_job_scores.sql`
- Create: `gateway/app/models/resume_job_score_model.py`

**Steps**
1. Write the SQL migration (see spec §9). Wrap in `BEGIN; ... COMMIT;`. Include `ALTER TABLE applications ALTER COLUMN ai_match_score DROP DEFAULT`.
2. Write `ResumeJobScoreModel` (see spec §4.3). Match the import style of `gateway/app/models/job_stage_model.py`.
3. Static import smoke check inside the gateway container:
   ```
   docker exec docker-backend-router-1 python -c "from app.models.resume_job_score_model import ResumeJobScoreModel; print('OK', ResumeJobScoreModel.__tablename__)"
   ```
4. Print the manual psql command for the user. Do not run.

**Done when:** model imports cleanly; migration file ready to apply.

### Slice B — Resume-parser `/score-fit` endpoint
**Files**
- Modify: `services/resume-parser/app/api.py`
- Modify: `services/resume-parser/app/inference.py`
- Create: `services/resume-parser/tests/test_score_fit.py`

**Steps**
1. In `inference.py`, add a function `run_score_inference(system_prompt: str, user_payload: str, backend: str = 'gemini') -> dict` that calls Gemini 2.5 Flash with `response_mime_type: 'application/json'`. Reuse the existing client setup; just generalize the system-prompt argument.
2. In `api.py`, add the `ScoreFitRequest`, `ScoreFitResponse` Pydantic schemas exactly as in spec §5.1.
3. Add the `POST /score-fit` handler:
   - Build the user payload: `f"Job:\n{json.dumps(job, indent=2)}\n\nResume:\n{json.dumps(resume, indent=2)}"`.
   - Call `run_score_inference(SCORE_SYSTEM_PROMPT, user_payload)`.
   - Validate: each integer key clamped to [0, 100]; `rationale` defaults to empty string if missing; raise `HTTPException(502, "scoring_unavailable")` on malformed JSON or missing `overall`.
4. Define `SCORE_SYSTEM_PROMPT` as a module-level constant in `api.py`, exactly the prompt frozen in spec §5.2.
5. Write tests in `tests/test_score_fit.py`:
   - `test_clamps_over_100_to_100`
   - `test_clamps_below_0_to_0`
   - `test_502_on_missing_overall`
   - `test_502_on_non_integer_overall`
   - `test_returns_validated_dict_on_success`
   Mock the Gemini call (monkeypatch `run_score_inference`).
6. Run tests. Build/restart the resume-parser container.

**Done when:** `pytest services/resume-parser/tests/test_score_fit.py -v` passes; endpoint returns 200 on a valid mocked call.

---

## Wave 2 — Gateway integration (after Wave 1)

### Slice C — Gateway scoring service + upload-resume integration
**Files**
- Create: `gateway/app/services/resume_scoring.py`
- Modify: `gateway/app/routes/job.py` (the `upload-resume` handler)
- Create: `gateway/tests/test_resume_scoring.py`

**Steps**
1. Write `resume_scoring.py` with `async def score_resume_for_job(resume: dict, job: dict) -> Optional[int]` exactly per spec §6.2. Use the existing `RESUME_PARSER_URL` env var pattern.
2. In `routes/job.py` `upload_resume` handler:
   - Add `job_id: Optional[UUID] = Form(None)` to the function signature (it's a multipart endpoint per the existing handler).
   - After parse succeeds, if `job_id` is not None:
     - Look up the job via `db.query(JobModel).filter_by(id=job_id, status='OPEN').first()`. If missing, log warning and skip (do NOT 4xx — upload still succeeds).
     - Build `job_payload = {"title": job.title, "description": job.description, "required_skills": job.required_skills, "experience_level": job.experience_level, "location": job.location, "type": job.type}`.
     - `score = await score_resume_for_job(parsed_resume, job_payload)`.
     - If `score is not None`: upsert `resume_job_scores`:
       ```python
       from sqlalchemy.dialects.postgresql import insert
       stmt = insert(ResumeJobScoreModel).values(resume_id=resume.id, job_id=job_id, overall=score)
       stmt = stmt.on_conflict_do_update(index_elements=['resume_id', 'job_id'], set_={'overall': score, 'updated_at': func.now()})
       db.execute(stmt)
       db.commit()
       ```
3. Tests in `gateway/tests/test_resume_scoring.py`:
   - `test_score_returns_int_on_success` — mock `httpx.AsyncClient.post` to return `{"overall": 72, ...}`. Assert returns 72.
   - `test_score_returns_none_on_502` — mock returns 502. Assert returns None.
   - `test_score_clamps_to_100` — mock returns `{"overall": 150, ...}`. Assert returns 100.
   - `test_score_returns_none_on_missing_overall` — mock returns `{"foo": 1}`. Assert returns None.
4. Run tests. Copy modified files into the gateway container, restart, verify logs.

**Done when:** unit tests pass; uploading a resume with a `job_id` writes a `resume_job_scores` row.

### Slice D — Apply flow copy-to-application
**Files**
- Modify: `gateway/app/routes/job.py` (the `apply_to_job` handler)
- Create: `gateway/tests/test_apply_with_score.py`

**Steps**
1. In `apply_to_job`, right before the `ApplicationModel(...)` constructor:
   ```python
   from ..models.resume_job_score_model import ResumeJobScoreModel  # add import at top
   score_row = (
       db.query(ResumeJobScoreModel)
       .filter_by(resume_id=resume.id, job_id=application_data.job_id)
       .first()
   )
   ai_match_score = score_row.overall if score_row else None
   ```
2. Pass `ai_match_score=ai_match_score` in the `ApplicationModel(...)` constructor (alongside the existing args from the kanban bugfix).
3. Tests:
   - `test_apply_copies_score_when_present` — seed a `resume_job_scores(overall=72)` row, POST /apply, assert created application's `ai_match_score == 72`.
   - `test_apply_leaves_null_when_no_score` — no score row. POST /apply. Assert `ai_match_score IS NULL`.
4. Run tests. Restart gateway container.

**Done when:** apply correctly copies (or leaves NULL) the score.

---

## Wave 3 — Frontend wire-up (after Wave 2)

### Slice E — Apply modal passes job_id on upload
**Files**
- Modify: `frontend/src/components/ApplyJobModal.tsx`

**Steps**
1. Locate the existing upload `fetch` / `apiRequest` call to `/job/upload-resume`.
2. The endpoint accepts multipart form data (per the existing handler). Add the `job_id` field to the FormData:
   ```tsx
   const formData = new FormData();
   formData.append('file', file);
   formData.append('job_id', jobId);   // NEW
   ```
3. `npm run build` clean.
4. Manual smoke: log in as candidate, apply to a job, upload resume, check Postgres: `SELECT * FROM resume_job_scores ORDER BY created_at DESC LIMIT 1;` → should show the resume's overall.

**Done when:** uploading inside the apply modal produces a row in `resume_job_scores`; submitting the apply produces an `applications` row with `ai_match_score` populated.

---

## Wave 4 — Verification

- Apply migration: `cat .\database\migrations\add_resume_job_scores.sql | docker exec -i docker-postgres-1 psql -U admin -d aicruit`.
- `docker compose -f infra/docker/docker-compose.yml restart resume-parser gateway` (or `docker restart docker-resume-parser-1 docker-backend-router-1`).
- Manual: candidate apply → check `resume_job_scores` and `applications.ai_match_score`.
- Recruiter view: open the job's kanban → AI score is NOT rendered anywhere (per spec §3 / §7).

## Out of scope (deferred)

- Recruiter dashboard ranking by `ai_match_score` (separate feature).
- Re-score on JD edit.
- Persisting sub-scores or rationale.
- Backfill for pre-existing applications.
