# Recruiter Kanban Stages — Design Spec

**Status:** Approved (brainstorm complete)
**Date:** 2026-05-01
**Branch:** `job-application-improvments`

## 1. Goal

Replace the recruiter's flat applicants table on the job-detail page with a kanban-style board of recruiter-defined hiring stages. Add a bulk auto-scheduler for AI interviews that spreads candidates across a date range with a 1-day per-candidate validity window.

## 2. Scope

In scope:
- Per-job, recruiter-named stages with stable IDs.
- Drag-and-drop kanban board on `/recruiter/job/[id]`.
- Stage editor on `/recruiter/job/[id]/interview-settings` (replaces the numeric "Number of interview stages" input).
- Auto-schedule dialog for AI interviews (front-loaded distribution; 1-day expiry per candidate).
- Real expiry enforcement at `/interview/start`.
- Removal of AI match score from recruiter views.

Out of scope:
- Real-time multi-recruiter sync (no websockets; refetch on focus is enough).
- Candidate-side UX changes beyond the new expiry on the interview start endpoint.
- Reworking the candidate's interview lifecycle states beyond adding `expired`.

## 3. User-facing behavior

### 3.1 Stages on a job
- Stages are recruiter-named per job and have stable UUIDs.
- Default seed (on job create): AI off → `[Applied, Shortlisted]`. AI on → `[Applied, AI Interview, Shortlisted]`.
- Toggling `ai_interview_enabled` after job creation does **not** add or remove stages automatically. A toast suggests adding an AI Interview stage manually.
- Stage editor (interview-settings page): badge row, inline rename, hover-delete, "+ Add stage" with name suggestions (`Applied`, `Phone Screen`, `AI Interview`, `Technical`, `Final`, `Offer` — first unused suggestion fills in).
- Editing rules:
  - Rename: always allowed.
  - Add: append or insert anywhere.
  - Reorder: allowed; candidates keep their stage assignment (FK is by stage ID, not position).
  - Delete a stage with candidates: prompt "Move N candidates to: [dropdown of remaining stages]".

### 3.2 Kanban board
- Replaces the existing `<Table>` of applicants on `/recruiter/job/[id]`.
- One column per stage, ordered by `position`.
- A virtual **Rejected** lane on the right is always present, collapsible. Toggle: "Show rejected (N)".
- Card content: candidate name, email, applied date, AI interview status pill (when relevant), download-resume icon, "View" link. **No AI match score.**
- AI interview status pill states (read from `interviews` row):
  - No record → no pill.
  - `scheduled` and not started → blue "Scheduled · May 5".
  - `in_progress` → amber "In progress".
  - `completed` → green "Completed" (clicks through to report).
  - `expired` → red "Expired".

### 3.3 Drag-and-drop
- Drag a card between stages → optimistic move + `PATCH .../stage`.
- Drag to Rejected lane → optimistic + `PATCH .../stage` with `{rejected: true}`. Server sets `applications.status = 'REJECTED'`, leaves `stage_id` intact.
- Drag out of Rejected lane back into a stage → `{stage_id: X, rejected: false}`. Server sets `status = stages[X].name`, `stage_id = X`.
- On error: rollback + toast + refetch.
- AI interview completion does **not** auto-advance the candidate; recruiter drags manually.

### 3.4 Auto-schedule (AI interview)
- Button visible in board header **only when `ai_interview_enabled = true`**.
- Click opens dialog: stage dropdown (this job's stages) + date range (`start_date`, `end_date`).
- Live preview (debounced `GET /preview`) shows distribution: "Day 1 (May 5): 5. Day 2: 5. Day 3: 5. Day 4: 4. Day 5: 4." plus skipped reasons.
- Confirm → `POST /auto-schedule`. Toast: "Scheduled N candidates across D days."
- Distribution: front-loaded, integer division with extras on earlier days. 23 ÷ 5 → 5,5,5,4,4.
- Validity window per candidate: 00:00 to 23:59:59 of their assigned day, in the **job's timezone**.
- Re-running the dialog only schedules **unscheduled** candidates (those with no active interview record). Already-scheduled candidates are skipped with reason.
- If a candidate misses their day: card shows "Expired" pill; recruiter sees it and decides manually (no auto-rejection, no auto-rollover).

## 4. Data model

### 4.1 New table: `job_stages`
```
id          UUID PK (gen_random_uuid())
job_id      UUID FK -> jobs(id) ON DELETE CASCADE
position    INT NOT NULL  (0-based; UNIQUE per job_id)
name        VARCHAR(100) NOT NULL
created_at  TIMESTAMPTZ DEFAULT now()
updated_at  TIMESTAMPTZ DEFAULT now()
UNIQUE (job_id, position)
INDEX (job_id)
```

### 4.2 `applications` changes
- `+ stage_id UUID NULL FK -> job_stages(id) ON DELETE SET NULL`
- `+ INDEX (job_id, stage_id)`
- Drop the existing `CHECK (status IN ('APPLIED', ...))` constraint.
- Add a relaxed `CHECK (status IS NOT NULL)` so legacy readers still see non-null values.
- `status` becomes a denormalized mirror of the stage name (or the literal `'REJECTED'`). Writers update both columns in the same tx.

### 4.3 `interviews` changes
- `+ expires_at TIMESTAMPTZ NULL`. NULL = no expiry (legacy/manual schedules); set by auto-schedule.
- The existing `'expired'` value in the status enum starts being used. Lazy transition on read of `/interview/start`.

### 4.4 `jobs` changes
- `+ timezone VARCHAR(64) NOT NULL DEFAULT 'UTC'`. Used to compute the day window for auto-schedule.

### 4.5 Compatibility / coexistence
- `GET /job/{id}` keeps its current applicants payload unchanged. New `/job/{id}/board` endpoint is purely additive.
- `PUT /job/{id}/interview-settings` continues to accept `interview_stages` (int) in the body; it is written to the existing column but no longer read by the frontend. Stages are managed via the dedicated stage CRUD endpoints.
- Existing `POST /interview/schedule` is unchanged. Auto-schedule reuses the same internal code path and additionally writes `expires_at`.
- Manual interviews (no `expires_at`) skip the expiry check at `/interview/start`.

## 5. API surface

All endpoints on the gateway. Auth: `RoleChecker(["RECRUITER","ADMIN"])`. Ownership enforced against `job.recruiter_id`.

### 5.1 Stage CRUD (`gateway/app/routes/job.py`)
| Method | Path | Body / Query | Returns |
|---|---|---|---|
| `GET` | `/job/{job_id}/stages` | — | `[{id, position, name}]` ordered by `position` |
| `POST` | `/job/{job_id}/stages` | `{name, position?}` | new stage; appended if `position` omitted |
| `PATCH` | `/job/{job_id}/stages/{stage_id}` | `{name?}` | renamed stage |
| `PUT` | `/job/{job_id}/stages/reorder` | `[{id, position}, ...]` (full set) | full ordered list (atomic) |
| `DELETE` | `/job/{job_id}/stages/{stage_id}?move_to={target_id}` | — | 204 on success, 409 with `{candidate_count}` if candidates present and `move_to` missing |

### 5.2 Candidate stage assignment
| Method | Path | Body | Returns |
|---|---|---|---|
| `PATCH` | `/job/{job_id}/applications/{application_id}/stage` | `{stage_id: UUID \| null, rejected?: bool}` | updated application |

Semantics:
- `{stage_id: X, rejected: false}` → `status = stages[X].name`, `stage_id = X`.
- `{rejected: true}` → `status = 'REJECTED'`; `stage_id` left unchanged.
- `{stage_id: X, rejected: false}` after rejection → un-rejects.

### 5.3 Board fetch
| Method | Path | Returns |
|---|---|---|
| `GET` | `/job/{job_id}/board` | `{stages: [{id, position, name, candidates: [...]}], rejected: [...]}` |

### 5.4 AI auto-schedule (`gateway/app/routes/interview.py` or new module)
| Method | Path | Body / Query | Returns |
|---|---|---|---|
| `POST` | `/job/{job_id}/auto-schedule` | `{stage_id, start_date, end_date}` (dates in job tz) | `{assigned: [{application_id, day, expires_at}], skipped: [{application_id, reason}]}` |
| `GET` | `/job/{job_id}/auto-schedule/preview` | query: `stage_id, start_date, end_date` | same shape, no DB writes |

Behavior:
- Eligible candidates: in `stage_id`, `status != 'REJECTED'`, no `interviews` row with status `scheduled` or `in_progress` (expired/cancelled rows are ignored).
- Front-loaded distribution: extras land on earlier days.
- For each: insert `interviews` row with `scheduled_at = day 00:00 (job tz)`, `expires_at = day 23:59:59 (job tz)`, `status = 'scheduled'`. Single tx.
- 422 on: empty stage, start > end, AI not enabled on job.

### 5.5 Interview start expiry
- In existing `/interview/start` handler: after auth/lookup, if `expires_at IS NOT NULL AND now() > expires_at`, set `status = 'expired'` and return **410 Gone** with `{detail: "Interview window expired"}`. Lazy update — no background worker.

## 6. Frontend

### 6.1 New components
- `frontend/src/components/kanban/KanbanBoard.tsx` — `DndContext`, `closestCorners`, fetches `['board', jobId]`.
- `frontend/src/components/kanban/StageColumn.tsx` — droppable column; header (name + count); `SortableContext` body.
- `frontend/src/components/kanban/CandidateCard.tsx` — sortable card. Shows name, email, applied date, AI interview pill, download-resume icon, "View" link. **No AI match score.**
- `frontend/src/components/kanban/RejectedLane.tsx` — collapsible right-side lane.
- `frontend/src/components/kanban/AutoScheduleDialog.tsx` — stage picker + date range + live preview.
- `frontend/src/components/stages/StageEditor.tsx` — badge row with inline rename, hover delete, "+ Add stage" + suggestions.
- `frontend/src/components/stages/DeleteStageDialog.tsx` — "Move N candidates to: [dropdown]" prompt on delete.

### 6.2 Modified files
- `frontend/src/app/recruiter/job/[id]/page.tsx` — replace the applicants `<Table>` with `<KanbanBoard jobId={id} />` and the auto-schedule button (gated on `ai_interview_enabled`). Keep the rest of the page.
- `frontend/src/app/recruiter/job/[id]/interview-settings/page.tsx` — replace the numeric "Number of interview stages" input with `<StageEditor jobId={id} />`. Add a hint banner ("Use Auto-schedule on the board to assign candidates to days.") when `ai_interview_enabled` is on.
- `frontend/src/lib/api.ts` — typed helpers: `getBoard`, `moveCandidate`, `getStages`, `addStage`, `renameStage`, `reorderStages`, `deleteStage`, `autoSchedule`, `previewAutoSchedule`.
- Strip AI match score from any other recruiter view that currently renders it (search-and-strip pass during impl: candidate row in any list, candidate detail header, etc.).

### 6.3 State management
- TanStack Query keys: `['board', jobId]`, `['stages', jobId]`. Both invalidated on stage edits and drags.
- Drag = optimistic update; rollback on error.
- Reorder stages = optimistic; server `PUT /reorder` is atomic.

### 6.4 New dependencies
- `@dnd-kit/core` and `@dnd-kit/sortable` (frontend).

## 7. Edge cases

- Empty stage selected for auto-schedule → 422.
- Date range start > end → 422.
- All candidates already scheduled (re-run case) → 200 with `assigned: []`.
- AI interview disabled on the job → 403 from auto-schedule; button hidden in UI.
- Candidate's prior interview is expired/cancelled → eligible for re-scheduling.
- Recruiter changes job timezone after auto-schedule has run → existing `expires_at` values are absolute timestamps and are not recomputed.
- Two recruiters dragging the same candidate concurrently → last write wins; refetch reconciles.
- Two recruiters reordering stages concurrently → position uniqueness per (job_id, position); conflicting reorder returns 409 and frontend refetches.
- Delete-with-`move_to` referencing a stage that no longer exists → 422.

## 8. Migration

`database/migrations/add_kanban_stages.sql`:
```sql
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

ALTER TABLE applications ADD COLUMN IF NOT EXISTS stage_id UUID
  REFERENCES job_stages(id) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_applications_job_stage ON applications(job_id, stage_id);

ALTER TABLE applications DROP CONSTRAINT IF EXISTS applications_status_check;
ALTER TABLE applications ADD CONSTRAINT applications_status_not_null CHECK (status IS NOT NULL);

ALTER TABLE interviews ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS timezone VARCHAR(64) NOT NULL DEFAULT 'UTC';
```

`database/migrations/backfill_kanban_stages.py` (idempotent):
1. For each job without rows in `job_stages`:
   - Read its `job_interview_settings.ai_interview_enabled`.
   - Insert default seed: AI off → `[Applied, Shortlisted]`; AI on → `[Applied, AI Interview, Shortlisted]`.
2. For each application with `stage_id IS NULL`:
   - Map legacy `status` to a stage on its job:
     - `APPLIED`, `SCREENING` → first stage.
     - `INTERVIEW_SCHEDULED`, `INTERVIEW_COMPLETED` → middle stage if AI on, else last.
     - `OFFERED` → last stage.
     - `REJECTED` → leave `stage_id` NULL; keep `status = 'REJECTED'`.

Per CLAUDE.md, migrations are applied manually against the running Postgres.

## 9. Testing

Project has no test infrastructure today. Establish minimal coverage for this feature only:

**Backend** — add `pytest` + `httpx.AsyncClient` + `pytest-asyncio` to `gateway/`. New `gateway/tests/test_kanban.py`:
- Stage CRUD: create, rename, reorder, delete-with-candidates returns 409, delete-with-`move_to` succeeds.
- Drag candidate updates `stage_id` and `status` mirror.
- Drag to rejected sets `status='REJECTED'`, leaves `stage_id`.
- Auto-schedule: 23 ÷ 5 → `[5,5,5,4,4]`; skip already-scheduled; 422 on bad ranges; 403 when AI disabled.
- `/interview/start` returns 410 when `expires_at < now`; passes when `expires_at IS NULL`.
- RBAC: candidate role gets 403 on stage endpoints.

**Frontend** — add `vitest` + `@testing-library/react`:
- `StageEditor`: add/rename/delete-with-prompt.
- `KanbanBoard`: drag fires the right mutation (mocked).
- `AutoScheduleDialog`: front-loaded preview matches the server response.

**Manual smoke** — docker compose up, exercise board + drag + auto-schedule + expiry + delete-with-move.

## 10. Rollout

Single PR on the existing `job-application-improvments` branch:
1. Apply SQL migration to dev DB.
2. Backend: stage CRUD + board + auto-schedule + expiry enforcement.
3. Frontend: StageEditor + KanbanBoard + AutoScheduleDialog.
4. Strip AI match score from other recruiter views.
5. Replace the applicants `<Table>` on the job-detail page.

## 11. Open / deferred

- Eventual cleanup: drop `applications.status` once no readers depend on it. Out of scope for this spec.
- AI interview lifecycle (in-progress → completed transitions, kickoff hooks) untouched here.
- Real-time multi-recruiter sync deferred.
- Stage templates (org-wide reusable stage sets) deferred.
