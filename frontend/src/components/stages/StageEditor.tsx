'use client';

import * as React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  DndContext,
  PointerSensor,
  KeyboardSensor,
  useSensor,
  useSensors,
  closestCenter,
  type DragEndEvent,
} from '@dnd-kit/core';
import {
  SortableContext,
  horizontalListSortingStrategy,
  useSortable,
  arrayMove,
  sortableKeyboardCoordinates,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { GripVertical, Plus, X } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';
import { stagesApi, type JobStage, ApiError } from '@/lib/api';
import { DeleteStageDialog } from './DeleteStageDialog';

const STAGE_SUGGESTIONS = [
  'Applied',
  'Phone Screen',
  'AI Interview',
  'Technical',
  'Final',
  'Offer',
];

interface StageChipProps {
  stage: JobStage;
  jobId: string;
  onRequestDelete: (stage: JobStage, candidateCount: number) => void;
}

function StageChip({ stage, jobId, onRequestDelete }: StageChipProps) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = React.useState(false);
  const [draftName, setDraftName] = React.useState(stage.name);

  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: stage.id });

  React.useEffect(() => {
    setDraftName(stage.name);
  }, [stage.name]);

  const renameMutation = useMutation({
    mutationFn: (name: string) => stagesApi.rename(jobId, stage.id, name),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stages', jobId] });
    },
  });

  const removeMutation = useMutation({
    mutationFn: () => stagesApi.remove(jobId, stage.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stages', jobId] });
    },
    onError: (err: unknown) => {
      if (err instanceof ApiError && err.status === 409) {
        const anyErr = err as ApiError & { body?: { candidate_count?: number } };
        const count = anyErr.body?.candidate_count ?? 0;
        onRequestDelete(stage, count);
        return;
      }
      // Try to parse candidate_count from message as fallback
      onRequestDelete(stage, 0);
    },
  });

  const commitRename = () => {
    const trimmed = draftName.trim();
    if (!trimmed || trimmed === stage.name) {
      setDraftName(stage.name);
      setEditing(false);
      return;
    }
    renameMutation.mutate(trimmed);
    setEditing(false);
  };

  const cancelRename = () => {
    setDraftName(stage.name);
    setEditing(false);
  };

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <div
      ref={setNodeRef}
      style={style}
      className="group relative inline-flex"
      data-testid={`stage-chip-${stage.id}`}
    >
      <Badge
        variant="soft"
        className="flex items-center gap-1.5 px-2 py-1 text-sm"
      >
        <button
          type="button"
          aria-label={`Drag ${stage.name}`}
          className="cursor-grab text-muted-foreground hover:text-foreground"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-3.5 w-3.5" />
        </button>
        {editing ? (
          <Input
            autoFocus
            value={draftName}
            onChange={(e) => setDraftName(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                e.preventDefault();
                commitRename();
              } else if (e.key === 'Escape') {
                e.preventDefault();
                cancelRename();
              }
            }}
            className="h-6 w-32 px-1 py-0 text-sm"
            aria-label={`Rename ${stage.name}`}
          />
        ) : (
          <button
            type="button"
            className="cursor-text bg-transparent text-inherit"
            onClick={() => setEditing(true)}
            aria-label={`Rename stage ${stage.name}`}
          >
            {stage.name}
          </button>
        )}
        <button
          type="button"
          aria-label={`Delete ${stage.name}`}
          className="ml-1 rounded-sm text-muted-foreground opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100 focus:opacity-100"
          onClick={() => removeMutation.mutate()}
          disabled={removeMutation.isPending}
        >
          <X className="h-3.5 w-3.5" />
        </button>
      </Badge>
    </div>
  );
}

export interface StageEditorProps {
  jobId: string;
}

export function StageEditor({ jobId }: StageEditorProps) {
  const queryClient = useQueryClient();
  const { data: stages, isLoading, isError } = useQuery({
    queryKey: ['stages', jobId],
    queryFn: () => stagesApi.list(jobId),
  });

  const [deleteTarget, setDeleteTarget] = React.useState<{
    stage: JobStage;
    candidateCount: number;
  } | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const reorderMutation = useMutation({
    mutationFn: (items: Array<{ id: string; position: number }>) =>
      stagesApi.reorder(jobId, items),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stages', jobId] });
    },
  });

  const createMutation = useMutation({
    mutationFn: (name: string) => stagesApi.create(jobId, { name }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['stages', jobId] });
    },
  });

  const ordered = React.useMemo(() => {
    if (!stages) return [];
    return [...stages].sort((a, b) => a.position - b.position);
  }, [stages]);

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;
    const oldIndex = ordered.findIndex((s) => s.id === active.id);
    const newIndex = ordered.findIndex((s) => s.id === over.id);
    if (oldIndex === -1 || newIndex === -1) return;
    const next = arrayMove(ordered, oldIndex, newIndex).map((s, i) => ({
      id: s.id,
      position: i,
    }));
    reorderMutation.mutate(next);
  };

  const handleAdd = () => {
    const used = new Set(
      (stages ?? []).map((s) => s.name.trim().toLowerCase()),
    );
    const suggestion =
      STAGE_SUGGESTIONS.find((n) => !used.has(n.toLowerCase())) ??
      `Stage ${(stages?.length ?? 0) + 1}`;
    createMutation.mutate(suggestion);
  };

  if (isLoading) {
    return (
      <div className="flex flex-wrap items-center gap-2">
        {Array.from({ length: 3 }).map((_, i) => (
          <Skeleton key={i} className="h-7 w-24 rounded-full" />
        ))}
      </div>
    );
  }

  if (isError) {
    return <p className="text-sm text-destructive">Failed to load stages</p>;
  }

  const otherStages = deleteTarget
    ? ordered.filter((s) => s.id !== deleteTarget.stage.id)
    : [];

  return (
    <>
      <div className="flex flex-wrap items-center gap-2 overflow-x-auto">
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={ordered.map((s) => s.id)}
            strategy={horizontalListSortingStrategy}
          >
            {ordered.map((stage) => (
              <StageChip
                key={stage.id}
                stage={stage}
                jobId={jobId}
                onRequestDelete={(s, count) =>
                  setDeleteTarget({ stage: s, candidateCount: count })
                }
              />
            ))}
          </SortableContext>
        </DndContext>
        <Button
          variant="outline"
          size="sm"
          onClick={handleAdd}
          disabled={createMutation.isPending}
        >
          <Plus className="mr-1 h-3.5 w-3.5" />
          Add stage
        </Button>
      </div>

      {deleteTarget && (
        <DeleteStageDialog
          jobId={jobId}
          stageId={deleteTarget.stage.id}
          stageName={deleteTarget.stage.name}
          candidateCount={deleteTarget.candidateCount}
          otherStages={otherStages}
          open={!!deleteTarget}
          onOpenChange={(o) => {
            if (!o) setDeleteTarget(null);
          }}
          onDeleted={() => {
            queryClient.invalidateQueries({ queryKey: ['stages', jobId] });
            queryClient.invalidateQueries({ queryKey: ['board', jobId] });
          }}
        />
      )}
    </>
  );
}

export default StageEditor;
