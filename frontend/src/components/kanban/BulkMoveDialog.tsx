'use client';

import * as React from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { toast } from 'sonner';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { boardApi, type BulkMoveResponse } from '@/lib/api';

interface Props {
  jobId: string;
  sourceStage: { id: string; name: string };
  nextStage: { id: string; name: string };
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onMoved: () => void;
}

export function BulkMoveDialog({
  jobId,
  sourceStage,
  nextStage,
  open,
  onOpenChange,
  onMoved,
}: Props) {
  const [minScore, setMinScore] = React.useState(70);
  const [debounced, setDebounced] = React.useState(70);

  React.useEffect(() => {
    const t = setTimeout(() => setDebounced(minScore), 300);
    return () => clearTimeout(t);
  }, [minScore]);

  const preview = useQuery<BulkMoveResponse>({
    queryKey: [
      'bulkMovePreview',
      jobId,
      sourceStage.id,
      debounced,
      nextStage.id,
    ],
    queryFn: () =>
      boardApi.bulkMovePreview(jobId, sourceStage.id, {
        min_score: debounced,
        target_stage_id: nextStage.id,
      }),
    enabled:
      open &&
      Number.isFinite(debounced) &&
      debounced >= 0 &&
      debounced <= 100,
    staleTime: 0,
  });

  const mutation = useMutation({
    mutationFn: () =>
      boardApi.bulkMove(jobId, sourceStage.id, {
        min_score: debounced,
        target_stage_id: nextStage.id,
      }),
    onSuccess: (data) => {
      try {
        toast.success(
          `Moved ${data.moved.length} candidate(s) to ${nextStage.name}`,
        );
      } catch {
        // ignore toast errors in tests
      }
      onMoved();
      onOpenChange(false);
    },
    onError: (e: unknown) => {
      const msg = e instanceof Error ? e.message : 'Failed to move candidates';
      try {
        toast.error(msg);
      } catch {
        // ignore
      }
    },
  });

  const moved = preview.data?.moved.length ?? 0;
  const belowThreshold =
    preview.data?.skipped.filter((s) => s.reason === 'below_threshold')
      .length ?? 0;
  const noScore =
    preview.data?.skipped.filter((s) => s.reason === 'no_score').length ?? 0;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>
            Move from {sourceStage.name} → {nextStage.name}
          </DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div>
            <Label htmlFor="min_score">Minimum AI score</Label>
            <Input
              id="min_score"
              type="number"
              min={0}
              max={100}
              value={minScore}
              onChange={(e) =>
                setMinScore(
                  Math.max(0, Math.min(100, Number(e.target.value) || 0)),
                )
              }
            />
          </div>
          <div className="text-sm">
            {preview.isLoading && (
              <span className="text-muted-foreground">Calculating…</span>
            )}
            {preview.data && (
              <>
                <p>
                  <strong>{moved}</strong> candidate(s) will move to{' '}
                  <strong>{nextStage.name}</strong>.
                </p>
                <p className="text-muted-foreground">
                  {belowThreshold} below threshold, {noScore} have no score.
                </p>
              </>
            )}
            {preview.isError && (
              <p className="text-red-600">Failed to load preview.</p>
            )}
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button
            onClick={() => mutation.mutate()}
            disabled={mutation.isPending || moved === 0}
          >
            {mutation.isPending ? 'Moving…' : `Move ${moved}`}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default BulkMoveDialog;
