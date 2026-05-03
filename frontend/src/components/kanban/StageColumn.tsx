'use client';

import * as React from 'react';
import { useDroppable } from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { useQueryClient } from '@tanstack/react-query';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { JobStage, BoardCandidate } from '@/lib/api';
import { CandidateCard } from './CandidateCard';
import { BulkMoveDialog } from './BulkMoveDialog';

export type BoardStage = JobStage & { candidates: BoardCandidate[] };

interface StageColumnProps {
  stage: BoardStage;
  jobId: string;
  nextStage?: { id: string; name: string } | null;
}

export function StageColumn({ stage, jobId, nextStage }: StageColumnProps) {
  const { setNodeRef, isOver } = useDroppable({ id: `stage:${stage.id}` });
  const [bulkOpen, setBulkOpen] = React.useState(false);
  const queryClient = useQueryClient();

  return (
    <div
      ref={setNodeRef}
      data-testid={`stage-column-${stage.id}`}
      className={cn(
        'flex w-72 flex-shrink-0 flex-col rounded-lg border bg-muted/30 p-3 transition-colors',
        isOver && 'bg-muted/60 border-primary',
      )}
    >
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold">{stage.name}</h3>
        <div className="flex items-center gap-2">
          {nextStage && (
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs"
              onClick={() => setBulkOpen(true)}
              data-testid={`bulk-move-button-${stage.id}`}
            >
              Move by score
            </Button>
          )}
          <Badge variant="secondary" className="text-xs">
            {stage.candidates.length}
          </Badge>
        </div>
      </div>
      <SortableContext
        items={stage.candidates.map((c) => c.application_id)}
        strategy={verticalListSortingStrategy}
      >
        <div className="flex-1 min-h-[60px]">
          {stage.candidates.length === 0 ? (
            <div className="flex h-16 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
              Drop candidates here
            </div>
          ) : (
            stage.candidates.map((c) => (
              <CandidateCard key={c.application_id} candidate={c} />
            ))
          )}
        </div>
      </SortableContext>
      {nextStage && (
        <BulkMoveDialog
          jobId={jobId}
          sourceStage={{ id: stage.id, name: stage.name }}
          nextStage={nextStage}
          open={bulkOpen}
          onOpenChange={setBulkOpen}
          onMoved={() =>
            queryClient.invalidateQueries({ queryKey: ['board', jobId] })
          }
        />
      )}
    </div>
  );
}

export default StageColumn;
