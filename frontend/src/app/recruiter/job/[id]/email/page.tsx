'use client';

import { useState, useEffect, useMemo } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { useToast } from '@/hooks/use-toast';
import {
  ArrowLeft,
  Mail,
  Sparkles,
  Loader2,
  Send,
} from 'lucide-react';
import {
  api,
  boardApi,
  emailApi,
  stagesApi,
  type BoardResponse,
  type BoardCandidate,
  type JobStage,
} from '@/lib/api';

const STATUS_OPTIONS = [
  { value: '', label: 'Any status' },
  { value: 'APPLIED', label: 'Applied' },
  { value: 'SCREENING', label: 'Screening' },
  { value: 'INTERVIEW_SCHEDULED', label: 'Interview Scheduled' },
  { value: 'INTERVIEW_COMPLETED', label: 'Interview Completed' },
  { value: 'OFFERED', label: 'Offered' },
  { value: 'REJECTED', label: 'Rejected' },
];

const SCENARIO_BY_STATUS: Record<string, string> = {
  APPLIED: 'shortlisted',
  SCREENING: 'shortlisted',
  INTERVIEW_SCHEDULED: 'interview_scheduled',
  INTERVIEW_COMPLETED: 'stage_advance',
  OFFERED: 'offer',
  REJECTED: 'rejection',
};

// Template-substitution helper that mirrors the backend's SafeDict semantics.
function renderTemplate(template: string, vars: Record<string, string>): string {
  if (!template) return '';
  return template.replace(/\{(\w+)\}/g, (_m, key) => {
    if (key in vars) return vars[key] ?? '';
    return `{${key}}`;
  });
}

interface CategoryScore {
  category: string;
  score: number;
}

export default function BulkEmailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const { toast } = useToast();

  const [jobTitle, setJobTitle] = useState<string>('');
  const [companyName, setCompanyName] = useState<string>('');
  const [board, setBoard] = useState<BoardResponse | null>(null);
  const [stages, setStages] = useState<JobStage[]>([]);
  const [loading, setLoading] = useState(true);

  const [statusFilter, setStatusFilter] = useState<string>('');
  const [stageFilter, setStageFilter] = useState<string>('');

  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [drafting, setDrafting] = useState(false);
  const [sending, setSending] = useState(false);
  const [includeScore, setIncludeScore] = useState(false);

  const [previewBody, setPreviewBody] = useState<string>('');
  const [previewLoading, setPreviewLoading] = useState(false);
  const [sampleScores, setSampleScores] = useState<CategoryScore[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        const [job, b, s] = await Promise.all([
          api.get<{ title: string; company_name?: string }>(`/job/${id}`),
          boardApi.get(id),
          stagesApi.list(id),
        ]);
        if (cancelled) return;
        setJobTitle(job.title || '');
        setCompanyName((job as any).company_name || '');
        setBoard(b);
        setStages(s);
      } catch (e) {
        toast({
          title: 'Error',
          description: 'Failed to load job data.',
          variant: 'destructive',
        });
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id, toast]);

  // Compute matched candidates client-side from the board.
  const matchedCandidates: BoardCandidate[] = useMemo(() => {
    if (!board) return [];
    const all: BoardCandidate[] = [
      ...board.stages.flatMap((s) => s.candidates),
      ...board.rejected,
    ];
    return all.filter((c) => {
      if (statusFilter && c.status !== statusFilter) return false;
      if (stageFilter && c.stage_id !== stageFilter) return false;
      return true;
    });
  }, [board, statusFilter, stageFilter]);

  const stageNameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of stages) map.set(s.id, s.name);
    return map;
  }, [stages]);

  // Sample preview using first matched candidate.
  useEffect(() => {
    if (!matchedCandidates.length) {
      setPreviewBody('');
      setSampleScores(null);
      return;
    }
    const first = matchedCandidates[0];
    const stageName = first.stage_id ? stageNameById.get(first.stage_id) ?? '' : '';
    const scheduledAt = first.interview?.scheduled_at ?? '';
    const vars = {
      candidate_name: first.candidate_name,
      job_title: jobTitle,
      company_name: companyName || 'AIcruit',
      stage_name: stageName,
      scheduled_at: scheduledAt,
    };
    let rendered = renderTemplate(body, vars);

    if (includeScore && statusFilter === 'REJECTED') {
      // Try to fetch the report for this application
      (async () => {
        try {
          setPreviewLoading(true);
          const details = await api.get<{ report?: { category_scores?: CategoryScore[] } }>(
            `/interview/${first.application_id}/details`,
          );
          const cs = details?.report?.category_scores ?? null;
          setSampleScores(cs);
          if (cs && cs.length) {
            const lines = ['', 'Performance Summary:'];
            for (const c of cs) {
              lines.push(`- ${c.category}: ${Number(c.score).toFixed(1)}/10`);
            }
            rendered = `${rendered.trimEnd()}\n${lines.join('\n')}`;
          }
          setPreviewBody(rendered);
        } catch {
          setPreviewBody(rendered);
          setSampleScores(null);
        } finally {
          setPreviewLoading(false);
        }
      })();
    } else {
      setPreviewBody(rendered);
      setSampleScores(null);
    }
  }, [
    matchedCandidates,
    body,
    includeScore,
    statusFilter,
    jobTitle,
    companyName,
    stageNameById,
  ]);

  const previewSubject = useMemo(() => {
    if (!matchedCandidates.length) return subject;
    const first = matchedCandidates[0];
    const stageName = first.stage_id ? stageNameById.get(first.stage_id) ?? '' : '';
    return renderTemplate(subject, {
      candidate_name: first.candidate_name,
      job_title: jobTitle,
      company_name: companyName || 'AIcruit',
      stage_name: stageName,
      scheduled_at: first.interview?.scheduled_at ?? '',
    });
  }, [matchedCandidates, subject, jobTitle, companyName, stageNameById]);

  const handleGenerate = async () => {
    setDrafting(true);
    try {
      const scenario =
        SCENARIO_BY_STATUS[statusFilter] ?? 'custom';
      const sample = matchedCandidates[0];
      const res = await emailApi.draft({
        scenario,
        application_id: sample?.application_id,
        include_interview_score: includeScore && scenario === 'rejection',
      });
      setSubject(res.subject);
      setBody(res.body);
    } catch (e) {
      toast({
        title: 'Error',
        description: 'Failed to generate email draft.',
        variant: 'destructive',
      });
    } finally {
      setDrafting(false);
    }
  };

  const handleSend = async () => {
    if (!matchedCandidates.length) return;
    if (!confirm(`Send email to ${matchedCandidates.length} candidate(s)?`)) return;
    setSending(true);
    try {
      const res = await emailApi.bulkSend({
        job_id: id,
        status: statusFilter || undefined,
        stage_id: stageFilter || undefined,
        subject_template: subject,
        body_template: body,
        include_interview_score: includeScore,
      });
      toast({
        title: 'Sent',
        description: `${res.sent} sent, ${res.failed} failed.`,
      });
      if (res.failed === 0) {
        router.push(`/recruiter/job/${id}`);
      }
    } catch (e: any) {
      toast({
        title: 'Error',
        description:
          e?.message?.includes('SMTP not configured')
            ? 'SMTP is not configured on the server.'
            : 'Failed to send emails.',
        variant: 'destructive',
      });
    } finally {
      setSending(false);
    }
  };

  if (loading) {
    return (
      <RecruiterLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      </RecruiterLayout>
    );
  }

  const isRejection = statusFilter === 'REJECTED';
  const previewCandidates = matchedCandidates.slice(0, 5);

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/recruiter/job/${id}`}>
              <ArrowLeft className="w-5 h-5" />
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold flex items-center gap-2">
              <Mail className="w-6 h-6" />
              Email Candidates
            </h1>
            <p className="text-muted-foreground text-sm mt-1">{jobTitle}</p>
          </div>
        </div>

        {/* Step 1: Filter */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">1. Choose recipients</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="grid gap-2">
                <Label htmlFor="status">Application status</Label>
                <select
                  id="status"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={statusFilter}
                  onChange={(e) => setStatusFilter(e.target.value)}
                >
                  {STATUS_OPTIONS.map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </div>
              <div className="grid gap-2">
                <Label htmlFor="stage">Hiring stage (optional)</Label>
                <select
                  id="stage"
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                  value={stageFilter}
                  onChange={(e) => setStageFilter(e.target.value)}
                >
                  <option value="">Any stage</option>
                  {stages.map((s) => (
                    <option key={s.id} value={s.id}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="rounded-md border bg-muted/30 p-3 text-sm">
              <p className="font-medium">
                {matchedCandidates.length} candidate
                {matchedCandidates.length === 1 ? '' : 's'} matched
              </p>
              {previewCandidates.length > 0 && (
                <ul className="mt-2 list-disc list-inside text-muted-foreground">
                  {previewCandidates.map((c) => (
                    <li key={c.application_id}>
                      {c.candidate_name}{' '}
                      <span className="text-xs">({c.candidate_email})</span>
                    </li>
                  ))}
                  {matchedCandidates.length > 5 && (
                    <li>...and {matchedCandidates.length - 5} more</li>
                  )}
                </ul>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Step 2: Compose */}
        <Card>
          <CardHeader>
            <CardTitle className="text-base">2. Compose email</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-2">
              <Label htmlFor="subject">Subject</Label>
              <Input
                id="subject"
                value={subject}
                onChange={(e) => setSubject(e.target.value)}
                placeholder="Update on your {job_title} application"
              />
            </div>
            <div className="grid gap-2">
              <div className="flex items-center justify-between">
                <Label htmlFor="body">Body</Label>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleGenerate}
                  disabled={drafting}
                >
                  {drafting ? (
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  ) : (
                    <Sparkles className="w-4 h-4 mr-2" />
                  )}
                  Generate with AI
                </Button>
              </div>
              <textarea
                id="body"
                className="flex min-h-[200px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                value={body}
                onChange={(e) => setBody(e.target.value)}
                placeholder="Hi {candidate_name}, ..."
              />
              <p className="text-xs text-muted-foreground">
                Template variables: {'{candidate_name}'}, {'{job_title}'},{' '}
                {'{company_name}'}, {'{stage_name}'}, {'{scheduled_at}'}
              </p>
            </div>

            {isRejection && (
              <div className="flex items-center justify-between rounded-md border p-3">
                <div className="space-y-0.5">
                  <Label className="text-sm font-medium">
                    Include AI interview category scores
                  </Label>
                  <p className="text-xs text-muted-foreground">
                    Append each candidate&apos;s performance summary to their email.
                  </p>
                </div>
                <Switch checked={includeScore} onCheckedChange={setIncludeScore} />
              </div>
            )}
          </CardContent>
        </Card>

        {/* Sample preview */}
        {(subject || body) && matchedCandidates.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-base">
                Sample preview ({matchedCandidates[0].candidate_name})
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div>
                <p className="text-xs text-muted-foreground">Subject</p>
                <p className="font-medium">{previewSubject || '(empty)'}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground">Body</p>
                {previewLoading ? (
                  <p className="text-sm text-muted-foreground">
                    Loading sample with scores...
                  </p>
                ) : (
                  <pre className="whitespace-pre-wrap text-sm font-sans bg-muted/30 rounded-md p-3 border">
                    {previewBody || '(empty)'}
                  </pre>
                )}
              </div>
              {includeScore && isRejection && sampleScores === null && !previewLoading && (
                <p className="text-xs text-muted-foreground">
                  No interview report found for this sample candidate.
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Step 3: Send */}
        <div className="flex justify-end gap-3">
          <Button variant="outline" asChild>
            <Link href={`/recruiter/job/${id}`}>Cancel</Link>
          </Button>
          <Button
            onClick={handleSend}
            disabled={
              sending ||
              !subject ||
              !body ||
              matchedCandidates.length === 0
            }
          >
            {sending ? (
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
            ) : (
              <Send className="w-4 h-4 mr-2" />
            )}
            Send to {matchedCandidates.length} candidate
            {matchedCandidates.length === 1 ? '' : 's'}
          </Button>
        </div>
      </div>
    </RecruiterLayout>
  );
}
