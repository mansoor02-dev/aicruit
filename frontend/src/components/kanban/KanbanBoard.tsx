'use client';

import * as React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
} from '@dnd-kit/core';
import { sortableKeyboardCoordinates } from '@dnd-kit/sortable';
import { toast } from 'sonner';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import {
  boardApi,
  ApiError,
  type BoardCandidate,
  type BoardResponse,
} from '@/lib/api';
import { StageColumn, type BoardStage } from './StageColumn';
import { RejectedLane } from './RejectedLane';
import { AutoScheduleDialog } from './AutoScheduleDialog';
import { KanbanJobIdContext } from './CandidateCard';

interface KanbanBoardProps {
  jobId: string;
  aiInterviewEnabled: boolean;
}

export interface MoveResult {
  stage_id: string | null;
  rejected: boolean;
}

/**
 * Compute the PATCH body for a drag-end event.
 * - Drop on `stage:<uuid>` → `{ stage_id: <uuid>, rejected: false }`
 * - Drop on `rejected` → `{ stage_id: <current stage_id>, rejected: true }`
 * - Drop on another candidate id → resolve to that candidate's container stage
 * - Otherwise → `null` (no-op)
 */
export function computeMove(
  candidate: BoardCandidate,
  overId: string | number | null | undefined,
  currentStages: BoardStage[],
): MoveResult | null {
  if (overId == null) return null;
  const idStr = String(overId);

  if (idStr === 'rejected') {
    return { stage_id: candidate.stage_id, rejected: true };
  }
  if (idStr.startsWith('stage:')) {
    return { stage_id: idStr.slice('stage:'.length), rejected: false };
  }
  // overId may be another candidate's application_id; resolve its stage.
  for (const stage of currentStages) {
    if (stage.candidates.some((c) => c.application_id === idStr)) {
      return { stage_id: stage.id, rejected: false };
    }
  }
  return null;
}

export function KanbanBoard({ jobId, aiInterviewEnabled }: KanbanBoardProps) {
  const queryClient = useQueryClient();
  const [autoOpen, setAutoOpen] = React.useState(false);

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['board', jobId],
    queryFn: () => boardApi.get(jobId),
  });

  const mutation = useMutation({
    mutationFn: ({
      applicationId,
      body,
    }: {
      applicationId: string;
      body: { stage_id: string | null; rejected?: boolean };
    }) => boardApi.moveCandidate(jobId, applicationId, body),
    onError: (err: unknown) => {
      const msg =
        err instanceof ApiError ? err.message : 'Failed to move candidate';
      try {
        toast.error(msg);
      } catch {
        // eslint-disable-next-line no-console
        console.error(msg);
      }
      queryClient.invalidateQueries({ queryKey: ['board', jobId] });
    },
  });

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || !data) return;
    const applicationId = String(active.id);

    let candidate: BoardCandidate | undefined;
    for (const s of data.stages) {
      const c = s.candidates.find((x) => x.application_id === applicationId);
      if (c) {
        candidate = c;
        break;
      }
    }
    if (!candidate) {
      candidate = data.rejected.find((x) => x.application_id === applicationId);
    }
    if (!candidate) return;

    const wasRejected = data.rejected.some(
      (x) => x.application_id === applicationId,
    );
    const move = computeMove(candidate, over.id, data.stages);
    if (!move) return;

    // No-op if dropping in same place (same stage, same rejected state)
    if (
      !move.rejected &&
      !wasRejected &&
      candidate.stage_id === move.stage_id
    ) {
      return;
    }
    if (move.rejected && wasRejected) return;

    // Optimistic update
    queryClient.setQueryData<BoardResponse>(['board', jobId], (prev) => {
      if (!prev) return prev;
      const stages = prev.stages.map((s) => ({
        ...s,
        candidates: s.candidates.filter(
          (c) => c.application_id !== applicationId,
        ),
      }));
      const rejected = prev.rejected.filter(
        (c) => c.application_id !== applicationId,
      );

      const updated: BoardCandidate = {
        ...candidate!,
        stage_id: move.stage_id,
        status: move.rejected ? 'REJECTED' : candidate!.status,
      };

      if (move.rejected) {
        rejected.unshift(updated);
      } else if (move.stage_id) {
        const idx = stages.findIndex((s) => s.id === move.stage_id);
        if (idx >= 0) stages[idx].candidates.unshift(updated);
      }

      return { stages, rejected };
    });

    mutation.mutate({
      applicationId,
      body: { stage_id: move.stage_id, rejected: move.rejected },
    });
  };

  if (isLoading) {
    return (
      <div className="flex gap-3 overflow-x-auto p-1">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-72 w-72 rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError || !data) {
    return (
      <p className="text-sm text-destructive">
        Failed to load board: {error instanceof Error ? error.message : 'Unknown error'}
      </p>
    );
  }

  return (
    <KanbanJobIdContext.Provider value={jobId}>
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <div className="text-sm text-muted-foreground">
            {data.stages.reduce((acc, s) => acc + s.candidates.length, 0)} candidates
          </div>
          {aiInterviewEnabled && (
            <Button
              type="button"
              size="sm"
              onClick={() => setAutoOpen(true)}
              data-testid="auto-schedule-button"
            >
              Auto-schedule AI interviews
            </Button>
          )}
        </div>
        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragEnd={handleDragEnd}
        >
          <div className="flex gap-3 overflow-x-auto p-1">
            {data.stages.map((stage, idx) => {
              const next = data.stages[idx + 1];
              return (
                <StageColumn
                  key={stage.id}
                  stage={stage as BoardStage}
                  jobId={jobId}
                  nextStage={next ? { id: next.id, name: next.name } : null}
                />
              );
            })}
            <RejectedLane candidates={data.rejected} />
          </div>
        </DndContext>
        {aiInterviewEnabled && (
          <AutoScheduleDialog
            jobId={jobId}
            stages={data.stages.map(({ id, position, name }) => ({
              id,
              position,
              name,
            }))}
            open={autoOpen}
            onOpenChange={setAutoOpen}
            onScheduled={() => {
              queryClient.invalidateQueries({ queryKey: ['board', jobId] });
            }}
          />
        )}
      </div>
    </KanbanJobIdContext.Provider>
  );
}

export default KanbanBoard;
