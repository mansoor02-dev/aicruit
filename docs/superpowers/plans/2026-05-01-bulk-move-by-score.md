# Bulk Move by AI Score — Implementation Plan

> Wave-based plan for parallel execution. Spec at `docs/superpowers/specs/2026-05-01-bulk-move-by-score-design.md`.

**Goal:** Show AI score on kanban cards; add per-stage bulk-promote-by-score dialog.

**Architecture:** No schema change. New `bulk-move` + `preview` endpoints. Extend `BoardCandidate` with `ai_match_score`. Frontend gains a card badge + a column-header button + a small dialog.

**Tech Stack:** FastAPI + SQLAlchemy + Next.js + @dnd-kit + TanStack Query.

---

## Wave 1 — Backend + Frontend foundation (parallel)

### Slice A — Backend: extend board + bulk-move endpoints
**Files**
- Modify: `gateway/app/models/application.py` — add `ai_match_score: Optional[int]` to `BoardCandidate`. Add new schemas: `BulkMoveRequest`, `BulkMoveSkipped`, `BulkMoveResponse`.
- Modify: `gateway/app/routes/job.py` — board endpoint serializer must include `ai_match_score` from `ApplicationModel.ai_match_score`. Add new endpoints `POST /{job_id}/stages/{stage_id}/bulk-move` and `GET /{job_id}/stages/{stage_id}/bulk-move/preview`.
- Create: `gateway/app/services/bulk_move.py` — service layer with one pure function and one writer:
  ```python
  def compute_bulk_move(applications, source_stage, target_stage, min_score) -> BulkMoveResponse:
      # pure: returns moved/skipped without DB writes
  def execute_bulk_move(db, job_id, stage_id, min_score, target_stage_id) -> BulkMoveResponse:
      # transaction: load + compute + bulk update + commit
  ```
- Create: `gateway/tests/test_bulk_move.py` — six tests per spec §8.

**Steps**
1. Schemas in `application.py`. Imports `Optional`, `List`, `UUID`, `BaseModel`.
2. Update the board serializer (in `routes/job.py` `_build_board_candidate`) to set `ai_match_score=app.ai_match_score`.
3. Service `compute_bulk_move(applications, source_stage, target_stage, min_score)`:
   - Iterate applications, exclude `status == 'REJECTED'`.
   - If `app.ai_match_score is None` → skipped, reason `"no_score"`.
   - Elif `app.ai_match_score < min_score` → skipped, reason `"below_threshold"`.
   - Else → moved.
   - Return `BulkMoveResponse(moved=[...], skipped=[...], target_stage={"id": str(target.id), "name": target.name})`.
4. Service `execute_bulk_move(db, job_id, stage_id, min_score, target_stage_id)`:
   - Use `_get_owned_job` is the route's job; here load source by `(job_id, stage_id)` (404), load target by `target_stage_id` else compute next via `position+1` (422 if none).
   - Query applications in source.
   - Call `compute_bulk_move(...)` to get plan.
   - For each `application_id` in `moved`: `db.query(ApplicationModel).filter_by(id=...).update({'stage_id': target.id, 'status': target.name})`. Bulk-update via `db.query(ApplicationModel).filter(ApplicationModel.id.in_(moved_ids)).update({...}, synchronize_session=False)` is cheaper.
   - Commit.
   - Return the same `BulkMoveResponse`.
5. Routes:
   - `POST /{job_id}/stages/{stage_id}/bulk-move` calls `execute_bulk_move`.
   - `GET /{job_id}/stages/{stage_id}/bulk-move/preview` loads, computes, returns; no commit.
6. Tests: pure-function tests + integration tests against an in-memory mocked session, similar to existing `test_resume_scoring.py` pattern. Use `MagicMock` for the session where possible. For the integration-style tests, fall back to the same approach used in `test_apply_with_score.py`.

**Verification**
```
docker cp gateway/app/services/bulk_move.py docker-backend-router-1:/app/app/services/bulk_move.py
docker cp gateway/app/models/application.py docker-backend-router-1:/app/app/models/application.py
docker cp gateway/app/routes/job.py docker-backend-router-1:/app/app/routes/job.py
docker cp gateway/tests/test_bulk_move.py docker-backend-router-1:/app/tests/test_bulk_move.py
docker exec docker-backend-router-1 python -m pytest tests/test_bulk_move.py -v
docker restart docker-backend-router-1
docker logs docker-backend-router-1 --tail 15
```
All tests must pass. Logs must come up clean.

### Slice B — Frontend: badge on card + types
**Files**
- Modify: `frontend/src/lib/api.ts` — extend `BoardCandidate` interface with `ai_match_score?: number | null`. Add `boardApi.bulkMove` and `boardApi.bulkMovePreview` helpers.
- Modify: `frontend/src/components/kanban/CandidateCard.tsx` — render small `<Badge>` top-right with the score, color-banded.

**Steps**
1. In `lib/api.ts`:
   ```ts
   export interface BoardCandidate {
     // ...existing fields...
     ai_match_score?: number | null;
   }

   export interface BulkMoveSkipped {
     application_id: string;
     reason: 'no_score' | 'below_threshold';
     ai_match_score: number | null;
   }
   export interface BulkMoveResponse {
     moved: string[];
     skipped: BulkMoveSkipped[];
     target_stage: { id: string; name: string };
   }

   // Add to boardApi:
   bulkMove: (jobId: string, stageId: string, body: { min_score: number; target_stage_id?: string }) =>
     api.post<BulkMoveResponse>(`/job/${jobId}/stages/${stageId}/bulk-move`, body),
   bulkMovePreview: (jobId: string, stageId: string, params: { min_score: number; target_stage_id?: string }) => {
     const qs = new URLSearchParams({
       min_score: String(params.min_score),
       ...(params.target_stage_id ? { target_stage_id: params.target_stage_id } : {}),
     }).toString();
     return api.get<BulkMoveResponse>(`/job/${jobId}/stages/${stageId}/bulk-move/preview?${qs}`);
   },
   ```
2. In `CandidateCard.tsx`, add a small absolute-positioned `<Badge>` in top-right when `candidate.ai_match_score != null`:
   ```tsx
   {candidate.ai_match_score != null && (
     <Badge
       className={
         candidate.ai_match_score >= 70 ? 'bg-green-100 text-green-800' :
         candidate.ai_match_score >= 40 ? 'bg-amber-100 text-amber-800' :
         'bg-red-100 text-red-800'
       }
     >
       AI {candidate.ai_match_score}
     </Badge>
   )}
   ```
   Place it inside the card root with `relative` positioning + the badge with `absolute top-2 right-2`. If the existing card layout uses flex, drop a `Badge` in the header row instead — match the existing visual style.
3. `cd frontend && npm run build` — must succeed.

**Done when:** card renders the score badge; build clean.

---

## Wave 2 — Frontend dialog + column wiring (after Wave 1)

### Slice C — BulkMoveDialog + column-header button
**Files**
- Create: `frontend/src/components/kanban/BulkMoveDialog.tsx`
- Modify: `frontend/src/components/kanban/StageColumn.tsx` — add "Move by score" button to header.
- Modify: `frontend/src/components/kanban/KanbanBoard.tsx` — pass `stages` array to `StageColumn` so it can resolve the next stage / disable the button on the last stage.
- Create: `frontend/src/components/kanban/__tests__/BulkMoveDialog.test.tsx`

**Steps**
1. `BulkMoveDialog` props:
   ```ts
   interface Props {
     jobId: string;
     sourceStage: { id: string; name: string };
     nextStage: { id: string; name: string };
     open: boolean;
     onOpenChange: (open: boolean) => void;
     onMoved: () => void;
   }
   ```
   Body:
   - Input `min_score`, default `70`, type=number, min=0, max=100.
   - Debounced (300ms) `boardApi.bulkMovePreview(...)`.
   - Renders: "**{moved.length}** candidates will move to **{nextStage.name}**." + "{skipped.filter(reason==='below_threshold').length} below threshold, {skipped.filter(reason==='no_score').length} have no score."
   - Confirm button → `boardApi.bulkMove(...)` → toast → `onMoved()` → close.
2. `StageColumn` header gets a small button when `nextStage` exists:
   ```tsx
   {nextStage && (
     <Button variant="ghost" size="sm" onClick={() => setBulkOpen(true)}>
       Move by score
     </Button>
   )}
   <BulkMoveDialog
     jobId={jobId}
     sourceStage={{ id: stage.id, name: stage.name }}
     nextStage={nextStage}
     open={bulkOpen}
     onOpenChange={setBulkOpen}
     onMoved={() => queryClient.invalidateQueries({ queryKey: ['board', jobId] })}
   />
   ```
3. `KanbanBoard`: when mapping `stages.map((s, idx) => <StageColumn ... nextStage={stages[idx+1]} />)`. Last stage receives `nextStage={undefined}`.
4. Tests:
   - Renders preview count from mocked `boardApi.bulkMovePreview`.
   - Confirm calls `boardApi.bulkMove` exactly once and `onMoved` once.
5. `cd frontend && npm run test -- --run src/components/kanban/__tests__/BulkMoveDialog.test.tsx`. All pass.
6. `npm run build`. Clean.

**Done when:** clicking "Move by score" in any non-last column opens the dialog; preview live-updates; confirm moves the right candidates server-side and the board refetches.

---

## Wave 3 — Smoke test

- Backend already restarted in Wave 1.
- In recruiter UI: open a job page, observe AI badges on cards. Click "Move by score" on the first stage. Set min=70. Confirm. Refresh — promoted candidates appear in the next stage.
- DB sanity: `SELECT id, status, stage_id, ai_match_score FROM applications WHERE job_id = '<id>' ORDER BY ai_match_score DESC NULLS LAST;`.

## Out of scope (deferred)

- Bulk reject by score (`<` threshold goes to Rejected lane). Easy follow-on.
- Sort the kanban column by score. Easy follow-on.
- Recruiter dashboard ranking by score. Separate spec.
