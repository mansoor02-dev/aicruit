'use client';

import { useState, useEffect, useMemo, KeyboardEvent } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { useQuery, useMutation } from '@tanstack/react-query';
import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { ArrowLeft, Loader2, Upload, X } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';
import { api } from '@/lib/api';
import { StageEditor } from '@/components/stages/StageEditor';

type Difficulty = 'low' | 'medium' | 'high' | 'very_high' | 'varying';

interface UploadedQuestion {
  question: string;
  topic?: string | null;
}

interface InterviewSettings {
  job_id: string;
  ai_interview_enabled: boolean;
  uploaded_questions: UploadedQuestion[] | null;
  topics: string[];
  fixed_question_count: boolean;
  number_of_questions: number | null;
  max_questions: number | null;
  difficulty_level: Difficulty | null;
  interview_stages: number;
}

const DIFFICULTY_OPTIONS: { value: Difficulty; label: string }[] = [
  { value: 'low', label: 'Low' },
  { value: 'medium', label: 'Medium' },
  { value: 'high', label: 'High' },
  { value: 'very_high', label: 'Very High' },
  { value: 'varying', label: 'Varying' },
];

function parseCsv(text: string): UploadedQuestion[] {
  const rows: UploadedQuestion[] = [];
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  for (const line of lines) {
    const cols: string[] = [];
    let cur = '';
    let inQuote = false;
    for (let i = 0; i < line.length; i++) {
      const ch = line[i];
      if (ch === '"') {
        if (inQuote && line[i + 1] === '"') {
          cur += '"';
          i++;
        } else {
          inQuote = !inQuote;
        }
      } else if (ch === ',' && !inQuote) {
        cols.push(cur);
        cur = '';
      } else {
        cur += ch;
      }
    }
    cols.push(cur);
    const q = (cols[0] || '').trim();
    const t = (cols[1] || '').trim();
    if (!q) continue;
    if (rows.length === 0 && /^question$/i.test(q) && /^topic$/i.test(t)) continue;
    rows.push({ question: q, topic: t || null });
  }
  return rows;
}

export default function InterviewSettingsPage() {
  const params = useParams();
  const id = params.id as string;
  const router = useRouter();
  const { toast } = useToast();

  const [aiEnabled, setAiEnabled] = useState(false);
  const [uploadedQuestions, setUploadedQuestions] = useState<UploadedQuestion[] | null>(null);
  const [uploadFileName, setUploadFileName] = useState<string>('');
  const [topics, setTopics] = useState<string[]>([]);
  const [topicInput, setTopicInput] = useState('');
  const [fixedCount, setFixedCount] = useState(false);
  const [numberOfQuestions, setNumberOfQuestions] = useState<string>('');
  const [maxQuestions, setMaxQuestions] = useState<string>('');
  const [difficulty, setDifficulty] = useState<Difficulty | ''>('');

  const { data, isLoading } = useQuery<InterviewSettings>({
    queryKey: ['interview-settings', id],
    queryFn: () => api.get(`/job/${id}/interview-settings`),
    enabled: !!id,
  });

  useEffect(() => {
    if (!data) return;
    setAiEnabled(!!data.ai_interview_enabled);
    setUploadedQuestions(data.uploaded_questions ?? null);
    setTopics(data.topics ?? []);
    setFixedCount(!!data.fixed_question_count);
    setNumberOfQuestions(data.number_of_questions?.toString() ?? '');
    setMaxQuestions(data.max_questions?.toString() ?? '');
    setDifficulty((data.difficulty_level as Difficulty) ?? '');
  }, [data]);

  const saveMutation = useMutation({
    mutationFn: (payload: Partial<InterviewSettings>) =>
      api.put(`/job/${id}/interview-settings`, payload),
    onSuccess: () => {
      toast({ title: 'Saved', description: 'Interview settings updated.' });
    },
    onError: (err: any) => {
      toast({
        title: 'Error',
        description: err?.message || 'Failed to save settings.',
        variant: 'destructive',
      });
    },
  });

  const addTopic = () => {
    const t = topicInput.trim();
    if (!t) return;
    if (topics.includes(t)) {
      setTopicInput('');
      return;
    }
    setTopics([...topics, t]);
    setTopicInput('');
  };

  const removeTopic = (t: string) => setTopics(topics.filter((x) => x !== t));

  const onTopicKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      addTopic();
    }
  };

  const handleFileUpload = async (file: File) => {
    setUploadFileName(file.name);
    const lower = file.name.toLowerCase();
    if (lower.endsWith('.csv')) {
      const text = await file.text();
      const rows = parseCsv(text);
      setUploadedQuestions(rows);
      toast({ title: 'Parsed', description: `${rows.length} questions loaded.` });
    } else if (lower.endsWith('.xlsx') || lower.endsWith('.xls')) {
      toast({
        title: 'Excel not parsed client-side',
        description:
          'CSV is parsed inline. For .xlsx/.xls, please save as CSV or wait for server-side support.',
        variant: 'destructive',
      });
    } else {
      toast({
        title: 'Unsupported file',
        description: 'Use .csv, .xlsx, or .xls.',
        variant: 'destructive',
      });
    }
  };

  const validate = (): string | null => {
    if (aiEnabled) {
      if (fixedCount) {
        const n = parseInt(numberOfQuestions, 10);
        if (!Number.isFinite(n) || n <= 0) return 'Number of questions is required.';
      } else {
        const n = parseInt(maxQuestions, 10);
        if (!Number.isFinite(n) || n <= 0) return 'Max questions is required.';
      }
    }
    return null;
  };

  const onSave = () => {
    const err = validate();
    if (err) {
      toast({ title: 'Invalid input', description: err, variant: 'destructive' });
      return;
    }
    saveMutation.mutate({
      ai_interview_enabled: aiEnabled,
      uploaded_questions: aiEnabled ? uploadedQuestions : null,
      topics: aiEnabled ? topics : [],
      fixed_question_count: fixedCount,
      number_of_questions:
        aiEnabled && fixedCount ? parseInt(numberOfQuestions, 10) : null,
      max_questions:
        aiEnabled && !fixedCount ? parseInt(maxQuestions, 10) : null,
      difficulty_level: aiEnabled ? (difficulty || null) : null,
    });
  };

  const previewQuestions = useMemo(
    () => (uploadedQuestions ?? []).slice(0, 5),
    [uploadedQuestions]
  );

  if (isLoading) {
    return (
      <RecruiterLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      </RecruiterLayout>
    );
  }

  return (
    <RecruiterLayout>
      <div className="space-y-6 max-w-3xl">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href={`/recruiter/job/${id}`}>
              <ArrowLeft className="w-5 h-5" />
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Interview Settings</h1>
            <p className="text-muted-foreground text-sm">
              Configure how this job&apos;s interviews are conducted.
            </p>
          </div>
        </div>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-lg">AI Interview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="flex items-center justify-between">
              <div>
                <Label className="text-base">Take AI Interview</Label>
                <p className="text-sm text-muted-foreground">
                  Run an automated AI interview for candidates of this job.
                </p>
              </div>
              <Switch checked={aiEnabled} onCheckedChange={setAiEnabled} />
            </div>

            {aiEnabled && (
              <>
                <div className="space-y-2">
                  <Label>Upload questions</Label>
                  <p className="text-xs text-muted-foreground">
                    .csv, .xlsx, .xls — first column is the question, second column is the topic.
                  </p>
                  <div className="flex items-center gap-3">
                    <Input
                      type="file"
                      accept=".csv,.xlsx,.xls"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        if (f) handleFileUpload(f);
                      }}
                    />
                    {uploadFileName && (
                      <span className="text-xs text-muted-foreground flex items-center gap-1">
                        <Upload className="w-3 h-3" />
                        {uploadFileName}
                      </span>
                    )}
                  </div>
                  {uploadedQuestions && uploadedQuestions.length > 0 && (
                    <div className="text-xs text-muted-foreground">
                      Loaded {uploadedQuestions.length} questions. Preview:
                      <ul className="list-disc list-inside mt-1 space-y-0.5">
                        {previewQuestions.map((q, i) => (
                          <li key={i}>
                            <span className="text-foreground">{q.question}</span>
                            {q.topic ? <span> — {q.topic}</span> : null}
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>

                <div className="space-y-2">
                  <Label>Topics to ask questions from</Label>
                  <div className="flex gap-2">
                    <Input
                      placeholder="Type a topic and press Enter"
                      value={topicInput}
                      onChange={(e) => setTopicInput(e.target.value)}
                      onKeyDown={onTopicKeyDown}
                    />
                    <Button type="button" variant="outline" onClick={addTopic}>
                      Add
                    </Button>
                  </div>
                  <div className="flex flex-wrap gap-2 pt-1">
                    {topics.map((t) => (
                      <Badge key={t} variant="secondary" className="gap-1">
                        {t}
                        <button
                          type="button"
                          onClick={() => removeTopic(t)}
                          className="ml-1 hover:text-destructive"
                          aria-label={`Remove ${t}`}
                        >
                          <X className="w-3 h-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <div>
                      <Label className="text-base">Fixed number of questions</Label>
                      <p className="text-sm text-muted-foreground">
                        If on, ask exactly N questions. If off, allow up to a maximum.
                      </p>
                    </div>
                    <Switch checked={fixedCount} onCheckedChange={setFixedCount} />
                  </div>

                  {fixedCount ? (
                    <div className="grid gap-2 max-w-xs">
                      <Label htmlFor="number_of_questions">Number of questions</Label>
                      <Input
                        id="number_of_questions"
                        type="number"
                        min={1}
                        value={numberOfQuestions}
                        onChange={(e) => setNumberOfQuestions(e.target.value)}
                      />
                    </div>
                  ) : (
                    <div className="grid gap-2 max-w-xs">
                      <Label htmlFor="max_questions">Max questions</Label>
                      <Input
                        id="max_questions"
                        type="number"
                        min={1}
                        value={maxQuestions}
                        onChange={(e) => setMaxQuestions(e.target.value)}
                      />
                    </div>
                  )}
                </div>

                <div className="grid gap-2 max-w-xs">
                  <Label>Difficulty level</Label>
                  <Select
                    value={difficulty || undefined}
                    onValueChange={(v) => setDifficulty(v as Difficulty)}
                  >
                    <SelectTrigger>
                      <SelectValue placeholder="Select difficulty" />
                    </SelectTrigger>
                    <SelectContent>
                      {DIFFICULTY_OPTIONS.map((opt) => (
                        <SelectItem key={opt.value} value={opt.value}>
                          {opt.label}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-lg">Interview Process</CardTitle>
            <p className="text-sm text-muted-foreground">
              Add and order the stages candidates pass through. Drag to reorder. Click a name to rename.
            </p>
          </CardHeader>
          <CardContent>
            {aiEnabled && (
              <div className="rounded-md border border-blue-200 bg-blue-50 p-3 text-sm text-blue-900 mb-3">
                Use Auto-schedule on the candidates board to assign AI interviews to days.
              </div>
            )}
            <StageEditor jobId={String(id)} />
          </CardContent>
        </Card>

        <div className="flex justify-end gap-3">
          <Button variant="outline" onClick={() => router.push(`/recruiter/job/${id}`)}>
            Cancel
          </Button>
          <Button onClick={onSave} disabled={saveMutation.isPending}>
            {saveMutation.isPending ? (
              <>
                <Loader2 className="w-4 h-4 mr-2 animate-spin" /> Saving...
              </>
            ) : (
              'Save Settings'
            )}
          </Button>
        </div>
      </div>
    </RecruiterLayout>
  );
}