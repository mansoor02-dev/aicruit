'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  ArrowLeft,
  HelpCircle,
  Mail,
  Phone,
  MapPin,
  Download,
  Briefcase,
  GraduationCap,
  FolderOpen,
  Sparkles,
  Calendar,
  Loader2,
  FileText,
  XCircle,
} from 'lucide-react';
import { format } from 'date-fns';
import { useToast } from '@/hooks/use-toast';
import { api, apiRequest } from '@/lib/api';
import { cn } from '@/lib/utils';

interface Education {
  university: string;
  degree: string;
  field: string;
  start_year: string;
  end_year: string;
}

interface Experience {
  title: string;
  company: string;
  start_date: string;
  end_date: string;
  description: string;
}

interface Project {
  title: string;
  description: string;
}

interface ApplicationQuestionDef {
  id: string;
  label: string;
  help_text?: string;
  type: string;
  required?: boolean;
  options?: string[];
}

interface QuestionResponse {
  question_id: string;
  label?: string;
  type?: string;
  value: string | number | boolean | null;
}

interface ApplicationDetail {
  application_id: string;
  job_id: string;
  job_title: string;
  application_status: string;
  ai_match_score: number;
  applied_at: string;
  applicant_name: string;
  applicant_email: string;
  applicant_phone: string;
  applicant_location: string;
  summary: string;
  skills: string[];
  education: Education[];
  experience: Experience[];
  projects: Project[];
  application_questions?: ApplicationQuestionDef[];
  question_responses?: QuestionResponse[];
  resume_id: string | null;
  resume_url: string;
}

const statusLabels: Record<string, string> = {
  'APPLIED': 'Applied',
  'SCREENING': 'Screening',
  'INTERVIEW_SCHEDULED': 'Interview Scheduled',
  'INTERVIEW_COMPLETED': 'Interview Completed',
  'OFFERED': 'Offered',
  'REJECTED': 'Rejected',
};

const statusColors: Record<string, string> = {
  'APPLIED': 'bg-gray-500/20 text-gray-400 border-gray-500/30',
  'SCREENING': 'bg-primary/20 text-blue-400 border-blue-500/30',
  'INTERVIEW_SCHEDULED': 'bg-warning/20 text-yellow-400 border-yellow-500/30',
  'INTERVIEW_COMPLETED': 'bg-indigo-500/20 text-indigo-400 border-indigo-500/30',
  'OFFERED': 'bg-success/20 text-green-400 border-green-500/30',
  'REJECTED': 'bg-destructive/20 text-red-400 border-red-500/30',
};

export default function CandidateDetailPage() {
  const params = useParams();
  const jobId = params.id as string;
  const applicationId = params.applicationId as string;
  const router = useRouter();
  const { toast } = useToast();

  const [data, setData] = useState<ApplicationDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [rejecting, setRejecting] = useState(false);

  useEffect(() => {
    const fetchDetail = async () => {
      try {
        setLoading(true);
        const response: ApplicationDetail = await api.get(`/job/application/${applicationId}`);
        setData(response);
      } catch (error) {
        console.error('Failed to fetch candidate details:', error);
        toast({
          title: 'Error',
          description: 'Failed to load candidate details.',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };
    fetchDetail();
  }, [applicationId, toast]);

  const handleReject = async () => {
    if (!data) return;
    if (!confirm('Reject this candidate? They will be moved to the Rejected lane.')) return;
    try {
      setRejecting(true);
      await apiRequest(
        `/job/${jobId}/applications/${data.application_id}/stage`,
        {
          method: 'PATCH',
          body: JSON.stringify({ rejected: true }),
        },
      );
      toast({ title: 'Candidate rejected' });
      router.push(`/recruiter/job/${jobId}`);
    } catch (err) {
      console.error('Reject failed', err);
      toast({
        title: 'Error',
        description: 'Failed to reject candidate.',
        variant: 'destructive',
      });
    } finally {
      setRejecting(false);
    }
  };

  if (loading) {
    return (
      <RecruiterLayout>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </RecruiterLayout>
    );
  }

  if (!data) {
    return (
      <RecruiterLayout>
        <div className="text-center py-20">
          <p className="text-muted-foreground text-lg">Candidate not found</p>
          <Button asChild className="mt-4">
            <Link href={`/recruiter/job/${jobId}`}>Back to Job</Link>
          </Button>
        </div>
      </RecruiterLayout>
    );
  }

  const safeDate = (val: string | null | undefined) => {
    if (!val) return 'â€”';
    const d = new Date(val);
    return isNaN(d.getTime()) ? 'â€”' : format(d, 'MMM d, yyyy');
  };

  const initials = data.applicant_name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <RecruiterLayout>
      <div className="max-w-5xl mx-auto space-y-6">
        {/* Back button */}
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => router.push(`/recruiter/job/${jobId}`)}>
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <p className="text-sm text-muted-foreground">Viewing application for</p>
            <h1 className="text-xl font-bold text-foreground">{data.job_title}</h1>
          </div>
        </div>

        {/* ===== Hero Card ===== */}
        <Card className="bg-gradient-to-br from-card to-primary/5 border-border overflow-hidden">
          <CardContent className="p-6 md:p-8">
            <div className="flex flex-col md:flex-row items-start md:items-center gap-6">
              {/* Avatar */}
              <div className="w-20 h-20 rounded-full bg-primary/15 border-2 border-primary/30 flex items-center justify-center text-2xl font-bold text-primary shrink-0">
                {initials}
              </div>

              {/* Name & Status */}
              <div className="flex-1 min-w-0">
                <div className="flex flex-wrap items-center gap-3 mb-2">
                  <h2 className="text-3xl font-extrabold tracking-tight text-foreground">{data.applicant_name}</h2>
                  <Badge
                    variant="outline"
                    className={cn('text-sm', statusColors[data.application_status])}
                  >
                    {statusLabels[data.application_status] || data.application_status}
                  </Badge>
                </div>

                <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <Mail className="w-4 h-4" />
                    {data.applicant_email}
                  </span>
                  {data.applicant_phone && (
                    <span className="flex items-center gap-1.5">
                      <Phone className="w-4 h-4" />
                      {data.applicant_phone}
                    </span>
                  )}
                  {data.applicant_location && (
                    <span className="flex items-center gap-1.5">
                      <MapPin className="w-4 h-4" />
                      {data.applicant_location}
                    </span>
                  )}
                  <span className="flex items-center gap-1.5">
                    <Calendar className="w-4 h-4" />
                    Applied {safeDate(data.applied_at)}
                  </span>
                </div>
              </div>

              {/* Resume */}
              <div className="flex flex-col items-end gap-3 shrink-0">
                {data.resume_url && (
                  <Button variant="outline" size="sm" asChild>
                    <a href={data.resume_url} target="_blank" rel="noopener noreferrer">
                      <Download className="w-4 h-4 mr-2" />
                      Download Resume
                    </a>
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ===== Summary ===== */}
        {data.summary && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary/10">
                  <FileText className="w-4 h-4 text-primary" />
                </div>
                Summary
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-foreground whitespace-pre-wrap leading-relaxed">{data.summary}</p>
            </CardContent>
          </Card>
        )}

        {/* ===== Skills ===== */}
        {data.skills && data.skills.length > 0 && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary/10">
                  <Sparkles className="w-4 h-4 text-primary" />
                </div>
                Skills
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {data.skills.map((skill, i) => (
                  <Badge
                    key={i}
                    variant="secondary"
                    className="px-3 py-1 text-sm font-medium bg-primary/10 text-primary border-primary/20"
                  >
                    {skill}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ===== Experience ===== */}
        {data.experience && data.experience.length > 0 && data.experience.some(e => e.title || e.company) && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary/10">
                  <Briefcase className="w-4 h-4 text-primary" />
                </div>
                Experience
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {data.experience
                .filter(exp => exp.title || exp.company)
                .map((exp, i) => (
                <div key={i} className="relative pl-6 border-l-2 border-primary/20 pb-1">
                  <div className="absolute -left-[7px] top-1 w-3 h-3 rounded-full bg-primary/40 border-2 border-card" />
                  <div className="space-y-1">
                    <h4 className="font-semibold text-foreground">{exp.title}</h4>
                    <p className="text-sm text-primary/80 font-medium">{exp.company}</p>
                    {(exp.start_date || exp.end_date) && (
                      <p className="text-xs text-muted-foreground">
                        {exp.start_date || 'â€”'} â†’ {exp.end_date || 'Present'}
                      </p>
                    )}
                    {exp.description && (
                      <p className="text-sm text-muted-foreground mt-2 whitespace-pre-wrap leading-relaxed">
                        {exp.description}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* ===== Education ===== */}
        {data.education && data.education.length > 0 && data.education.some(e => e.university || e.degree) && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary/10">
                  <GraduationCap className="w-4 h-4 text-primary" />
                </div>
                Education
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-5">
              {data.education
                .filter(edu => edu.university || edu.degree)
                .map((edu, i) => (
                <div key={i} className="relative pl-6 border-l-2 border-primary/20 pb-1">
                  <div className="absolute -left-[7px] top-1 w-3 h-3 rounded-full bg-primary/40 border-2 border-card" />
                  <div className="space-y-1">
                    <h4 className="font-semibold text-foreground">{edu.degree}{edu.field ? ` in ${edu.field}` : ''}</h4>
                    <p className="text-sm text-primary/80 font-medium">{edu.university}</p>
                    {(edu.start_year || edu.end_year) && (
                      <p className="text-xs text-muted-foreground">
                        {edu.start_year || 'â€”'} â†’ {edu.end_year || 'Present'}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        )}

        {/* ===== Projects ===== */}
        {data.projects && data.projects.length > 0 && data.projects.some(p => p.title) && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary/10">
                  <FolderOpen className="w-4 h-4 text-primary" />
                </div>
                Projects
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2">
                {data.projects
                  .filter(p => p.title)
                  .map((proj, i) => (
                  <div
                    key={i}
                    className="p-4 rounded-lg border border-border bg-background/50 space-y-2 hover:border-primary/30 transition-colors"
                  >
                    <h4 className="font-semibold text-foreground">{proj.title}</h4>
                    {proj.description && (
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap leading-relaxed">
                        {proj.description}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        )}

        {/* ===== Application Questions ===== */}
        {data.question_responses && data.question_responses.length > 0 && (
          <Card className="bg-card border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-base flex items-center gap-2">
                <div className="p-1.5 rounded-md bg-primary/10">
                  <HelpCircle className="w-4 h-4 text-primary" />
                </div>
                Application Questions
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-5">
                {data.question_responses.map((r, i) => {
                  const def = (data.application_questions || []).find((q) => q.id === r.question_id);
                  const label = (def?.label) || r.label || r.question_id;
                  const v = r.value;
                  let display: React.ReactNode;
                  if (v === null || v === undefined || v === "") {
                    display = <span className="italic text-muted-foreground">(no answer)</span>;
                  } else if (typeof v === "boolean") {
                    display = (
                      <Badge
                        variant="outline"
                        className={cn(
                          v
                            ? "bg-success/15 text-green-400 border-green-500/30"
                            : "bg-destructive/15 text-red-400 border-red-500/30",
                        )}
                      >
                        {v ? "Yes" : "No"}
                      </Badge>
                    );
                  } else {
                    display = (
                      <p className="text-foreground whitespace-pre-wrap leading-relaxed">
                        {String(v)}
                      </p>
                    );
                  }
                  return (
                    <div key={i} className="space-y-1">
                      <div className="text-sm font-medium text-muted-foreground">{label}</div>
                      <div>{display}</div>
                      {def?.help_text && (
                        <div className="text-xs text-muted-foreground/70">{def.help_text}</div>
                      )}
                    </div>
                  );
                })}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Bottom Actions */}
        <div className="flex flex-wrap justify-between items-center gap-3 pt-2 pb-8">
          <Button variant="outline" onClick={() => router.push(`/recruiter/job/${jobId}`)}>
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to Applicants
          </Button>
          <div className="flex items-center gap-2">
            {data.resume_url && (
              <Button asChild variant="outline">
                <a href={data.resume_url} target="_blank" rel="noopener noreferrer">
                  <Download className="w-4 h-4 mr-2" />
                  Download Resume
                </a>
              </Button>
            )}
            {data.application_status !== 'REJECTED' && (
              <Button
                variant="destructive"
                onClick={handleReject}
                disabled={rejecting}
              >
                <XCircle className="w-4 h-4 mr-2" />
                {rejecting ? 'Rejecting…' : 'Reject Candidate'}
              </Button>
            )}
          </div>
        </div>
      </div>
    </RecruiterLayout>
  );
}
