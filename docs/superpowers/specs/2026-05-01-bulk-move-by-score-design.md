# Kanban Bulk Move by AI Score — Design Spec

**Status:** Approved
**Date:** 2026-05-01
**Branch:** `job-application-improvments`
**Depends on:** kanban-stages spec, ai-resume-fit-score spec.

## 1. Goal

Surface the per-application AI fit score on the recruiter's kanban cards, and add a per-stage "Move by score" action that bulk-promotes candidates whose `ai_match_score >= threshold` to the next stage.

## 2. Scope

In: AI score badge on `CandidateCard`; bulk-move endpoint + preview; dialog UX in any column whose stage has a next stage.
Out: changes to candidate-side or to candidate detail page; new ranking/sorting; auto-promotion on apply.

## 3. User-facing behavior

- Each card shows a small badge top-right: `AI {score}`. Color: red <40, amber 40–69, green ≥70. NULL → no badge.
- Each `StageColumn` header shows a small "Move by score" ghost button. Disabled when the column is the last stage by position.
- Clicking opens a dialog: number input (min_score, default 70), live preview "N will move to **{nextStage.name}**. M skipped (no_score) / K below_threshold." Confirm fires the bulk move.

## 4. Data model

No schema change. The `applications.ai_match_score` column already exists and is populated by the AI resume-fit feature.

## 5. API surface

All on the gateway. Auth: `Depends(allow_recruiters)` + `_get_owned_job`. Reuses helpers from prior slices.

### 5.1 Modified: `GET /job/{job_id}/board`
- `BoardCandidate` schema gains `ai_match_score: Optional[int]`. Server-side reads `applications.ai_match_score` directly.
- All other fields unchanged.

### 5.2 New: `POST /job/{job_id}/stages/{stage_id}/bulk-move`
Body:
```python
class BulkMoveRequest(BaseModel):
    min_score: int  # 0..100
    target_stage_id: Optional[UUID] = None
```
Response:
```python
class BulkMoveSkipped(BaseModel):
    application_id: UUID
    reason: str           # "no_score" | "below_threshold"
    ai_match_score: Optional[int]

class BulkMoveResponse(BaseModel):
    moved: List[UUID]
    skipped: List[BulkMoveSkipped]
    target_stage: dict    # {id, name}
```
Logic in one tx:
1. Source stage looked up by `(job_id, stage_id)`. 404 if not on this job.
2. Target: if `target_stage_id` is None → next stage by `position + 1` of source on this job. 422 if no next stage.
3. Eligible = applications in source stage where `status != 'REJECTED'` AND `ai_match_score IS NOT NULL` AND `ai_match_score >= min_score`. Bulk-update their `stage_id` to target and `status` to target.name.
4. Skipped = applications in the source stage where `status != 'REJECTED'` AND (score IS NULL OR score < min_score). Each gets a reason.

### 5.3 New: `GET /job/{job_id}/stages/{stage_id}/bulk-move/preview`
Query params: `min_score`, `target_stage_id?`. Same response shape as bulk-move; no writes. Used by the dialog for live counts.

## 6. Frontend

- `frontend/src/lib/api.ts`: extend `BoardCandidate` with `ai_match_score?: number | null`. Extend `boardApi` with `bulkMove(jobId, stageId, body)` and `bulkMovePreview(jobId, stageId, params)`.
- `frontend/src/components/kanban/CandidateCard.tsx`: top-right badge `AI {score}`, color-banded.
- `frontend/src/components/kanban/StageColumn.tsx`: header "Move by score" `Button variant="ghost" size="sm"`, disabled when last stage. On click → opens `BulkMoveDialog`.
- New `frontend/src/components/kanban/BulkMoveDialog.tsx`:
  - Number input default 70. Debounced preview call. Confirm fires bulk-move and invalidates `['board', jobId]`.
  - Shows: moving count, skipped breakdown by reason, optional collapsed list of moving candidate names.

## 7. Edge cases

- Source stage is last → backend 422 `no_next_stage`; frontend disables button to prevent the call.
- Source stage empty → preview shows zeros; Confirm still allowed (no-op).
- `min_score` outside 0..100 → 422 from backend; frontend clamps via input min/max.
- Concurrent moves by another recruiter → server is single tx; client refetches on success.
- Candidate is REJECTED → never included.
- `target_stage_id` references a stage from another job → 404.

## 8. Testing

Backend (`gateway/tests/test_bulk_move.py`):
- `test_bulk_move_promotes_above_threshold`
- `test_bulk_move_excludes_null_scores`
- `test_bulk_move_excludes_rejected`
- `test_bulk_move_422_on_last_stage`
- `test_bulk_move_resolves_next_stage_when_target_omitted`
- `test_bulk_move_preview_does_not_write`

Frontend (`frontend/src/components/kanban/__tests__/BulkMoveDialog.test.tsx`):
- Renders preview count from mocked API.
- Confirm calls `bulkMove` once and triggers `onMoved`.

Manual smoke: docker compose up; recruiter views job, sees AI badges; clicks "Move by score" with min=70; chosen candidates move.

## 9. Rollout

Single PR. No migration. Order:
1. Backend: extend `BoardCandidate`, add `bulk-move` + `preview`.
2. Frontend: badge on card, button on column header, dialog.
3. Restart gateway container; `npm run build`.

## 10. Out of scope (deferred)

- Sorting by score in any view.
- Bulk-reject via threshold.
- Per-stage configurable default thresholds.
