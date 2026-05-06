'use client';

import * as React from 'react';
import { useRouter } from 'next/navigation';
import { useSortable } from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import { Download, FileText, GripVertical } from 'lucide-react';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { BoardCandidate } from '@/lib/api';

export const KanbanJobIdContext = React.createContext<string | null>(null);

interface CandidateCardProps {
  candidate: BoardCandidate;
  isOverlay?: boolean;
}

function formatDate(value: string): string {
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString(undefined, {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
    });
  } catch {
    return value;
  }
}

function formatScheduled(value: string): string {
  try {
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return value;
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  } catch {
    return value;
  }
}

interface PillSpec {
  className: string;
  label: string;
}

function pillFor(interview: NonNullable<BoardCandidate['interview']>): PillSpec | null {
  switch (interview.status) {
    case 'scheduled':
      return {
        className: 'bg-blue-100 text-blue-700 border-blue-200',
        label: `Scheduled · ${formatScheduled(interview.scheduled_at)}`,
      };
    case 'in_progress':
      return {
        className: 'bg-amber-100 text-amber-700 border-amber-200',
        label: 'In progress',
      };
    case 'completed':
      return {
        className: 'bg-green-100 text-green-700 border-green-200',
        label: 'Completed',
      };
    case 'expired':
      return {
        className: 'bg-red-100 text-red-700 border-red-200',
        label: 'Expired',
      };
    default:
      return null;
  }
}

export function CandidateCard({ candidate, isOverlay }: CandidateCardProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: candidate.application_id });

  const style: React.CSSProperties = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging && !isOverlay ? 0.4 : 1,
  };

  const pill = candidate.interview ? pillFor(candidate.interview) : null;
  const jobId = React.useContext(KanbanJobIdContext);
  const router = useRouter();
  const viewHref = jobId
    ? `/recruiter/job/${jobId}/candidate/${candidate.application_id}`
    : `/recruiter/applications/${candidate.application_id}`;

  const interviewCompleted =
    candidate.status === 'INTERVIEW_COMPLETED' ||
    candidate.interview?.status === 'completed';
  // The interview-details route is keyed by application_id (the gateway endpoint
  // /interview/{application_id}/details). Use application_id, not interview.id.
  const interviewDetailsKey = candidate.application_id;

  const handleCardClick = (e: React.MouseEvent) => {
    // Don't navigate if user is interacting with a button/link/etc.
    const target = e.target as HTMLElement;
    if (target.closest('button, a, [data-no-card-click="true"]')) return;
    router.push(viewHref);
  };

  return (
    <Card
      ref={setNodeRef}
      style={style}
      data-testid={`candidate-card-${candidate.application_id}`}
      onClick={handleCardClick}
      role="link"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === 'Enter') router.push(viewHref);
      }}
      className={cn(
        'p-3 mb-2 bg-card border shadow-sm cursor-pointer hover:border-primary/40 hover:shadow-md transition-all',
        isOverlay && 'shadow-lg',
      )}
    >
      <div className="flex items-start gap-2">
        <button
          type="button"
          aria-label={`Drag ${candidate.candidate_name}`}
          className="mt-0.5 cursor-grab text-muted-foreground hover:text-foreground"
          {...attributes}
          {...listeners}
        >
          <GripVertical className="h-4 w-4" />
        </button>
        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <div className="font-bold text-sm truncate">{candidate.candidate_name}</div>
            {candidate.ai_match_score != null && (
              <Badge
                variant="outline"
                className={cn(
                  'shrink-0 text-[10px] font-medium',
                  candidate.ai_match_score >= 70
                    ? 'bg-green-100 text-green-800 border-green-200'
                    : candidate.ai_match_score >= 40
                      ? 'bg-amber-100 text-amber-800 border-amber-200'
                      : 'bg-red-100 text-red-800 border-red-200',
                )}
              >
                AI {candidate.ai_match_score}
              </Badge>
            )}
          </div>
          <div className="text-xs text-muted-foreground truncate">
            {candidate.candidate_email}
          </div>
          <div className="text-xs text-muted-foreground mt-1">
            Applied {formatDate(candidate.applied_at)}
          </div>
          {pill && (
            <div className="mt-2">
              <Badge
                variant="outline"
                className={cn('text-[10px] font-medium', pill.className)}
              >
                {pill.label}
              </Badge>
            </div>
          )}
          <div className="mt-2 flex items-center gap-3 flex-wrap">
            {candidate.resume_url && (
              <a
                href={candidate.resume_url}
                target="_blank"
                rel="noreferrer"
                aria-label="Download resume"
                className="text-muted-foreground hover:text-foreground"
                onClick={(e) => e.stopPropagation()}
              >
                <Download className="h-3.5 w-3.5" />
              </a>
            )}
            {interviewCompleted && (
              <Button
                type="button"
                size="sm"
                variant="outline"
                className="h-7 px-2 text-[11px]"
                onClick={(e) => {
                  e.stopPropagation();
                  router.push(`/recruiter/interview-details/${interviewDetailsKey}`);
                }}
              >
                <FileText className="h-3 w-3 mr-1" />
                Interview Details
              </Button>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

export default CandidateCard;
