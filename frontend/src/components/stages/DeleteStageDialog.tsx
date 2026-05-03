'use client';

import * as React from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { stagesApi, type JobStage, ApiError } from '@/lib/api';

export interface DeleteStageDialogProps {
  jobId: string;
  stageId: string;
  stageName: string;
  candidateCount: number;
  otherStages: JobStage[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onDeleted: () => void;
}

export function DeleteStageDialog({
  jobId,
  stageId,
  stageName,
  candidateCount,
  otherStages,
  open,
  onOpenChange,
  onDeleted,
}: DeleteStageDialogProps) {
  const [selectedStageId, setSelectedStageId] = React.useState<string>(
    otherStages[0]?.id ?? '',
  );
  const [submitting, setSubmitting] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setSelectedStageId(otherStages[0]?.id ?? '');
      setError(null);
    }
  }, [open, otherStages]);

  const handleConfirm = async () => {
    if (!selectedStageId) {
      setError('Please pick a stage to move candidates to.');
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      await stagesApi.remove(jobId, stageId, selectedStageId);
      onDeleted();
      onOpenChange(false);
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : 'Failed to delete stage';
      setError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Delete stage</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <p className="text-sm">
            <strong>
              {candidateCount} candidate{candidateCount === 1 ? '' : 's'} are in stage &apos;{stageName}&apos;
            </strong>
            . Choose where to move them:
          </p>
          <select
            aria-label="Move candidates to"
            className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            value={selectedStageId}
            onChange={(e) => setSelectedStageId(e.target.value)}
            disabled={submitting || otherStages.length === 0}
          >
            {otherStages.length === 0 && <option value="">No other stages</option>}
            {otherStages.map((s) => (
              <option key={s.id} value={s.id}>
                {s.name}
              </option>
            ))}
          </select>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={submitting || !selectedStageId}
          >
            {submitting ? 'Moving...' : 'Move and Delete'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default DeleteStageDialog;
