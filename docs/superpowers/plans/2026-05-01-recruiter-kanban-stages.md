# Recruiter Kanban Stages — Implementation Plan

> **For agentic workers:** This plan is structured in **waves** for parallel execution. Slices within a wave are independent (different file trees / different services) and dispatched concurrently. Each wave depends on the previous wave being complete. Reference the design spec at `docs/superpowers/specs/2026-05-01-recruiter-kanban-stages-design.md` for full requirements.

**Goal:** Replace the recruiter's flat applicants table with a kanban board of recruiter-defined stages, plus an auto-scheduler for AI interviews with 1-day expiry windows.

**Architecture:** New `job_stages` table (per-job, stable IDs). `applications.stage_id` FK as source of truth, with `status` kept as a denormalized name mirror for legacy readers. New `expires_at` on `interviews`. New `timezone` on `jobs`. Frontend: `@dnd-kit` kanban board + badge-style stage editor.

**Tech Stack:** FastAPI + SQLAlchemy + Pydantic (gateway), Postgres, Next.js 14 + TanStack Query + shadcn/ui + `@dnd-kit` (frontend).

---

## Wave 1 — Foundation (parallel)

Two slices touch disjoint file trees and run in parallel.

### Slice A — Backend foundation
**Files**
- Create: `database/migrations/add_kanban_stages.sql`
- Create: `database/migrations/backfill_kanban_stages.py`
- Create: `gateway/app/models/job_stage_model.py` (`JobStageModel`)
- Create: `gateway/app/models/job_stage.py` (Pydantic schemas: `JobStageCreate`, `JobStageUpdate`, `JobStageResponse`, `StageReorderItem`)
- Modify: `gateway/app/models/application_model.py` — add `stage_id` column + relationship to `JobStageModel`.
- Modify: `gateway/app/models/job_model.py` — add `timezone` column + `stages` relationship.
- Modify: `gateway/app/models/interview_model.py` — add `expires_at` column.
- Modify: `gateway/app/models/job.py` — add `stage_id` to `ApplicantInfo`; remove `ai_match_score` from `ApplicantInfo`.

**Steps**
1. Write the SQL migration (see spec §8). Manually apply to local Postgres.
2. Write the SQLAlchemy `JobStageModel` mirroring the SQL.
3. Write Pydantic schemas.
4. Add `stage_id`, relationship to `ApplicationModel`.
5. Add `timezone`, `stages` relationship to `JobModel`.
6. Add `expires_at` to `InterviewModel`.
7. Update `ApplicantInfo` (add `stage_id`, remove `ai_match_score`).
8. Write the backfill script and run it.
9. Quick smoke: `python -c "from gateway.app.models.job_stage_model import JobStageModel; print(JobStageModel.__tablename__)"`.
10. Commit: `feat(backend): add kanban stages foundation (migration + models)`.

**Done when:** migration applied to dev DB; importing each model raises no error; existing endpoints still respond 200.

### Slice B — Frontend foundation
**Files**
- Modify: `frontend/package.json` — add `@dnd-kit/core`, `@dnd-kit/sortable`, `@dnd-kit/utilities`, `vitest`, `@testing-library/react`, `@testing-library/user-event`, `jsdom`.
- Create: `frontend/vitest.config.ts`.
- Modify: `frontend/src/lib/api.ts` — add typed helpers and TS types for the new endpoints.

**Steps**
1. `cd frontend && npm install @dnd-kit/core @dnd-kit/sortable @dnd-kit/utilities`.
2. `npm install -D vitest @testing-library/react @testing-library/user-event jsdom @vitest/ui`.
3. Add `vitest.config.ts` with `jsdom` env and `setupFiles`.
4. Add `frontend/src/test/setup.ts` (`import '@testing-library/jest-dom/vitest'`).
5. Add helpers to `lib/api.ts`: `getStages`, `addStage`, `renameStage`, `reorderStages`, `deleteStage`, `getBoard`, `moveCandidate`, `autoSchedule`, `previewAutoSchedule`. Each is a thin wrapper over `api.get/post/patch/put/delete`.
6. Add TS interface types: `JobStage`, `BoardCandidate`, `BoardResponse`, `AutoScheduleAssignment`, `AutoScheduleResponse`.
7. `npm run build` — must succeed.
8. Commit: `feat(frontend): add dnd-kit, vitest, kanban API helpers`.

**Done when:** `npm run build` clean; new helpers compile-check.

---

## Wave 2 — Endpoints + UI components (parallel after Wave 1)

Five slices. Three backend slices touch different routes files (or different functions in the same file but with no shared lines). Two frontend slices touch independent components.

### Slice C — Backend: stage CRUD endpoints
**Files**
- Modify: `gateway/app/routes/job.py` — append stage CRUD endpoints under `/job/{job_id}/stages`.
- Create: `gateway/app/services/job_stages.py` — service layer for create/rename/reorder/delete.

**Endpoints** (see spec §5.1 for shapes): `GET / POST / PATCH / PUT reorder / DELETE`.

**Steps**
1. Write service functions: `list_stages`, `create_stage`, `rename_stage`, `reorder_stages`, `delete_stage(move_to)`.
2. `delete_stage` raises a 409-mappable exception when candidates exist and `move_to` is None.
3. Wire endpoints with `Depends(allow_recruiters)` and ownership check (`job.recruiter_id == current_user.recruiter_id`).
4. Reorder validates that the body's id set equals the job's current set.
5. Hand-test with curl after starting the gateway.
6. Commit: `feat(backend): stage CRUD endpoints`.

### Slice D — Backend: candidate stage assignment + board fetch
**Files**
- Modify: `gateway/app/routes/job.py` — `PATCH /job/{job_id}/applications/{application_id}/stage`, `GET /job/{job_id}/board`.
- Modify: `gateway/app/services/applications.py` (or new file `gateway/app/services/board.py`) — query that joins applications + interviews + stages.

**Steps**
1. `PATCH .../stage` body: `{stage_id: UUID | null, rejected: bool = false}`. Update `applications.stage_id` and mirror `status` in same tx (use stage name or `'REJECTED'`).
2. `GET /board` returns `{stages: [{id, position, name, candidates: [...]}], rejected: [...]}` — single round-trip with eager-loaded interview rows for status pills.
3. Hand-test.
4. Commit: `feat(backend): candidate stage assignment + board fetch`.

### Slice E — Backend: auto-schedule + expiry enforcement
**Files**
- Modify: `gateway/app/routes/interview.py` — uncomment + replace the time-window check; add the auto-schedule endpoints.
- Create: `gateway/app/services/auto_schedule.py` — pure distribution function `distribute(candidates, days) -> List[Tuple[candidate, day_index]]` and the orchestration that writes interviews.

**Steps**
1. Pure distribution function: front-loaded integer split. e.g. `distribute(23, 5) == [5,5,5,4,4]`.
2. `POST /job/{job_id}/auto-schedule` and `GET /preview`. Use job timezone (from `JobModel.timezone`); compute `scheduled_at = day 00:00`, `expires_at = day 23:59:59` (in tz, then store as UTC).
3. Skip candidates with active interview (`status in ('scheduled','in_progress')`).
4. In `/interview/start`: replace the commented block (lines ~530-538 in the file) with `if interview.expires_at and datetime.now(timezone.utc) > interview.expires_at: interview.status = 'expired'; db.commit(); raise HTTPException(410, 'Interview window expired')`.
5. Hand-test with curl + a manually-aged `expires_at`.
6. Commit: `feat(backend): AI auto-schedule + interview expiry`.

### Slice F — Frontend: StageEditor + DeleteStageDialog
**Files**
- Create: `frontend/src/components/stages/StageEditor.tsx`.
- Create: `frontend/src/components/stages/DeleteStageDialog.tsx`.
- Create: `frontend/src/components/stages/__tests__/StageEditor.test.tsx`.

**Steps**
1. `StageEditor` props: `{ jobId: string }`. Uses TanStack Query `['stages', jobId]`. Renders a row of badges (each editable inline). "+ Add stage" button picks first unused name from `['Applied','Phone Screen','AI Interview','Technical','Final','Offer']`.
2. Hover delete icon → opens `DeleteStageDialog` if `candidates_in_stage > 0` (server returns 409 with count). Dialog asks "Move N candidates to: [dropdown]". On confirm, retries delete with `?move_to=...`.
3. Reorder: drag handle on each badge using `@dnd-kit/sortable`. On drop, fires `PUT /reorder`.
4. Tests: add badge, rename badge, delete-with-candidates shows dialog.
5. Commit: `feat(frontend): StageEditor + DeleteStageDialog`.

### Slice G — Frontend: KanbanBoard + cards + AutoScheduleDialog
**Files**
- Create: `frontend/src/components/kanban/KanbanBoard.tsx`.
- Create: `frontend/src/components/kanban/StageColumn.tsx`.
- Create: `frontend/src/components/kanban/CandidateCard.tsx`.
- Create: `frontend/src/components/kanban/RejectedLane.tsx`.
- Create: `frontend/src/components/kanban/AutoScheduleDialog.tsx`.
- Create: `frontend/src/components/kanban/__tests__/KanbanBoard.test.tsx`.

**Steps**
1. `KanbanBoard` props: `{ jobId: string, aiInterviewEnabled: boolean }`. Fetches `['board', jobId]`.
2. `DndContext` with `closestCorners`. Sensors: pointer + keyboard.
3. `onDragEnd`: optimistic update of cache + `PATCH .../stage`. Dropping over `RejectedLane` sends `{rejected: true}`.
4. `CandidateCard`: name, email, applied date, AI interview status pill (no AI match score). Pill color from `interview.status`. "Expired" badge when `interview.status === 'expired'`.
5. `AutoScheduleDialog`: stage select + start_date + end_date + debounced preview call. Confirm fires `POST /auto-schedule`, toasts result.
6. Tests: drag fires mutation; preview matches `[5,5,5,4,4]` for 23/5.
7. Commit: `feat(frontend): kanban board + auto-schedule dialog`.

**Done when:** components render in isolation (Storybook-style or test render); types align with API helpers.

---

## Wave 3 — Integration (parallel after Wave 2)

### Slice H — Wire StageEditor into interview-settings page
**Files**
- Modify: `frontend/src/app/recruiter/job/[id]/interview-settings/page.tsx` — replace the numeric "Number of interview stages" Input (lines ~390-408) with `<StageEditor jobId={id} />`. Drop the `stages` state. Stop sending `interview_stages` in the PUT body (server still accepts it for back-compat but no longer needs it).

**Steps**
1. Remove the existing `<Input id="interview_stages" .../>` block.
2. Drop `const [stages, setStages] = useState<string>('1')`, the `setStages(...)` line in the load effect, and the `interview_stages` field in the PUT payload.
3. Render `<StageEditor jobId={id} />` in the same Card.
4. Add a hint banner above the StageEditor when `ai_interview_enabled` is true: "Use Auto-schedule on the board to assign AI interviews to days."
5. `npm run build` clean.
6. Commit: `feat(frontend): swap numeric stages input for StageEditor`.

### Slice I — Wire KanbanBoard into job page; strip AI match score
**Files**
- Modify: `frontend/src/app/recruiter/job/[id]/page.tsx` — replace the applicants `<Table>` (and `statusLabels`/`statusColors` constants used only there) with `<KanbanBoard jobId={id} aiInterviewEnabled={...} />`. Add the Auto-schedule button in the page header when AI interview is enabled.
- Search-and-strip pass: any other recruiter view that renders `ai_match_score` (`frontend/src/app/recruiter/candidates/page.tsx`, `frontend/src/app/recruiter/job/[id]/candidate/[applicationId]/page.tsx`, etc.) — remove the column/badge.

**Steps**
1. Remove the `<Table>` of applicants and its supporting hooks/constants.
2. Render `<KanbanBoard jobId={id} aiInterviewEnabled={job.ai_interview_enabled} />`.
3. Add `<Button onClick={() => setAutoScheduleOpen(true)}>Auto-schedule AI interviews</Button>` in the page header, gated on `ai_interview_enabled`.
4. Grep for `ai_match_score` and `match_score` across `frontend/src/app/recruiter/`. Remove any UI that surfaces it. Keep API types if unused removal would break compilation; otherwise remove them too.
5. `npm run build` and manual smoke: docker compose up, log in as recruiter, drag a card, run auto-schedule.
6. Commit: `feat(frontend): kanban board on job page; remove AI match score from recruiter views`.

---

## Verification

- Backend: `pytest gateway/tests/test_kanban.py` (added by Slice C/D/E).
- Frontend: `cd frontend && npx vitest run`.
- Manual: docker compose up, exercise spec §3.

## Out of scope (deferred)

- Real-time multi-recruiter sync.
- Stage templates across jobs.
- Eventual removal of `applications.status` once readers migrate.
