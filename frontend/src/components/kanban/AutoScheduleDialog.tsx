'use client';

import * as React from 'react';
import { toast } from 'sonner';

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import {
  autoScheduleApi,
  ApiError,
  type JobStage,
  type AutoScheduleResponse,
} from '@/lib/api';

export interface AutoScheduleDialogProps {
  jobId: string;
  stages: JobStage[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onScheduled: () => void;
}

function formatDay(dateStr: string): string {
  try {
    const d = new Date(dateStr + 'T00:00:00');
    if (Number.isNaN(d.getTime())) return dateStr;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return dateStr;
  }
}

interface DayBucket {
  day: string;
  count: number;
}

function bucketize(assigned: AutoScheduleResponse['assigned']): DayBucket[] {
  const map = new Map<string, number>();
  for (const a of assigned) {
    map.set(a.day, (map.get(a.day) ?? 0) + 1);
  }
  return Array.from(map.entries())
    .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
    .map(([day, count]) => ({ day, count }));
}

export function AutoScheduleDialog({
  jobId,
  stages,
  open,
  onOpenChange,
  onScheduled,
}: AutoScheduleDialogProps) {
  const [stageId, setStageId] = React.useState<string>(stages[0]?.id ?? '');
  const [startDate, setStartDate] = React.useState<string>('');
  const [endDate, setEndDate] = React.useState<string>('');
  const [preview, setPreview] = React.useState<AutoScheduleResponse | null>(null);
  const [previewLoading, setPreviewLoading] = React.useState(false);
  const [previewError, setPreviewError] = React.useState<string | null>(null);
  const [submitting, setSubmitting] = React.useState(false);
  const [submitError, setSubmitError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (open) {
      setStageId(stages[0]?.id ?? '');
      setStartDate('');
      setEndDate('');
      setPreview(null);
      setPreviewError(null);
      setSubmitError(null);
    }
  }, [open, stages]);

  const inputsValid = React.useMemo(() => {
    if (!stageId || !startDate || !endDate) return false;
    return startDate <= endDate;
  }, [stageId, startDate, endDate]);

  React.useEffect(() => {
    if (!open) return;
    if (!inputsValid) {
      setPreview(null);
      setPreviewError(null);
      return;
    }
    let cancelled = false;
    setPreviewLoading(true);
    const handle = setTimeout(async () => {
      try {
        const res = await autoScheduleApi.preview(jobId, {
          stage_id: stageId,
          start_date: startDate,
          end_date: endDate,
        });
        if (!cancelled) {
          setPreview(res);
          setPreviewError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setPreview(null);
          setPreviewError(
            err instanceof ApiError ? err.message : 'Failed to load preview',
          );
        }
      } finally {
        if (!cancelled) setPreviewLoading(false);
      }
    }, 300);
    return () => {
      cancelled = true;
      clearTimeout(handle);
    };
  }, [open, jobId, stageId, startDate, endDate, inputsValid]);

  const buckets = preview ? bucketize(preview.assigned) : [];
  const skippedCount = preview?.skipped.length ?? 0;
  const totalAssigned = preview?.assigned.length ?? 0;
  const canConfirm = inputsValid && !submitting && totalAssigned > 0;

  const handleConfirm = async () => {
    if (!inputsValid) return;
    setSubmitting(true);
    setSubmitError(null);
    try {
      const res = await autoScheduleApi.run(jobId, {
        stage_id: stageId,
        start_date: startDate,
        end_date: endDate,
      });
      const days = bucketize(res.assigned).length;
      toast.success(
        `Scheduled ${res.assigned.length} candidates across ${days} day${days === 1 ? '' : 's'}`,
      );
      onScheduled();
      onOpenChange(false);
    } catch (err) {
      let msg = 'Failed to schedule';
      if (err instanceof ApiError) {
        if (err.status === 403) {
          msg = 'AI interview is not enabled for this job';
        } else {
          msg = err.message;
        }
      }
      setSubmitError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Auto-schedule AI interviews</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <div>
            <label className="text-sm font-medium" htmlFor="auto-schedule-stage">
              Stage
            </label>
            <select
              id="auto-schedule-stage"
              aria-label="Stage"
              className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
              value={stageId}
              onChange={(e) => setStageId(e.target.value)}
              disabled={submitting}
            >
              {stages.length === 0 && <option value="">No stages</option>}
              {stages.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-sm font-medium" htmlFor="auto-schedule-start">
                Start date
              </label>
              <input
                id="auto-schedule-start"
                aria-label="Start date"
                type="date"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={startDate}
                onChange={(e) => setStartDate(e.target.value)}
                disabled={submitting}
              />
            </div>
            <div>
              <label className="text-sm font-medium" htmlFor="auto-schedule-end">
                End date
              </label>
              <input
                id="auto-schedule-end"
                aria-label="End date"
                type="date"
                className="mt-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={endDate}
                onChange={(e) => setEndDate(e.target.value)}
                disabled={submitting}
              />
            </div>
          </div>
          <div className="rounded-md border bg-muted/30 p-3 text-sm" data-testid="preview">
            {!inputsValid && (
              <p className="text-muted-foreground">
                Pick a stage and a valid date range to preview.
              </p>
            )}
            {inputsValid && previewLoading && (
              <p className="text-muted-foreground">Loading preview...</p>
            )}
            {inputsValid && !previewLoading && previewError && (
              <p className="text-destructive">{previewError}</p>
            )}
            {inputsValid && !previewLoading && !previewError && preview && (
              <div className="space-y-1">
                {buckets.length === 0 ? (
                  <p className="text-muted-foreground">
                    No eligible candidates to schedule.
                  </p>
                ) : (
                  <ul className="space-y-0.5">
                    {buckets.map((b, i) => (
                      <li key={b.day}>
                        Day {i + 1} ({formatDay(b.day)}): {b.count} candidate
                        {b.count === 1 ? '' : 's'}.
                      </li>
                    ))}
                  </ul>
                )}
                {skippedCount > 0 && (
                  <p className="text-xs text-muted-foreground">
                    {skippedCount} skipped.
                  </p>
                )}
              </div>
            )}
          </div>
          {submitError && (
            <p className="text-sm text-destructive">{submitError}</p>
          )}
        </div>
        <DialogFooter>
          <Button
            variant="outline"
            onClick={() => onOpenChange(false)}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button onClick={handleConfirm} disabled={!canConfirm}>
            {submitting ? 'Scheduling...' : 'Confirm'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default AutoScheduleDialog;
