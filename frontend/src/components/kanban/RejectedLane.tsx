'use client';

import * as React from 'react';
import { useDroppable } from '@dnd-kit/core';
import {
  SortableContext,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { ChevronDown, ChevronRight } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { BoardCandidate } from '@/lib/api';
import { CandidateCard } from './CandidateCard';

interface RejectedLaneProps {
  candidates: BoardCandidate[];
}

export function RejectedLane({ candidates }: RejectedLaneProps) {
  const [open, setOpen] = React.useState(false);
  const { setNodeRef, isOver } = useDroppable({ id: 'rejected' });

  const count = candidates.length;

  return (
    <div
      ref={setNodeRef}
      data-testid="rejected-lane"
      className={cn(
        'flex w-72 flex-shrink-0 flex-col rounded-lg border border-dashed p-3 transition-colors',
        isOver && 'bg-red-50 border-red-300',
      )}
    >
      <Button
        type="button"
        variant="ghost"
        size="sm"
        onClick={() => setOpen((v) => !v)}
        className="mb-2 w-full justify-start gap-1 text-sm"
      >
        {open ? (
          <ChevronDown className="h-4 w-4" />
        ) : (
          <ChevronRight className="h-4 w-4" />
        )}
        {open ? 'Hide rejected' : 'Show rejected'} ({count})
      </Button>
      {open && (
        <SortableContext
          items={candidates.map((c) => c.application_id)}
          strategy={verticalListSortingStrategy}
        >
          <div className="flex-1 min-h-[60px]">
            {count === 0 ? (
              <div className="flex h-16 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">
                Drop to reject
              </div>
            ) : (
              candidates.map((c) => (
                <CandidateCard key={c.application_id} candidate={c} />
              ))
            )}
          </div>
        </SortableContext>
      )}
    </div>
  );
}

export default RejectedLane;
