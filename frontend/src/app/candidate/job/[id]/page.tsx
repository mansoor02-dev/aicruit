'use client';

import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { CandidateLayout } from '@/components/layout/CandidateLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import {
  ArrowLeft,
  Briefcase,
  Building2,
  Calendar,
  DollarSign,
  Loader2,
  MapPin,
} from 'lucide-react';
import { format } from 'date-fns';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { ApplyJobModal } from '@/components/ApplyJobModal';

type ApplicationQuestionType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'date'
  | 'select'
  | 'yes_no'
  | 'email'
  | 'url';

interface ApplicationQuestion {
  id: string;
  label: string;
  help_text?: string;
  type: ApplicationQuestionType;
  required: boolean;
  options?: string[];
}

interface JobDetail {
  id: string;
  title: string;
  description: string;
  location: string;
  type: string;
  salary_min: number | null;
  salary_max: number | null;
  required_skills: string[];
  experience_level: string;
  status: string;
  created_at: string;
  last_date_to_apply?: string | null;
  company_name?: string;
  application_questions?: ApplicationQuestion[];
}

export default function CandidateJobDetailPage() {
  const params = useParams();
  const id = params.id as string;
  const { toast } = useToast();

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [isApplyOpen, setIsApplyOpen] = useState(false);
  const [hasApplied, setHasApplied] = useState(false);

  useEffect(() => {
    if (!id) return;
    const fetchJob = async () => {
      try {
        setLoading(true);
        const res: JobDetail = await api.get(`/job/${id}`);
        setJob(res);
      } catch (err) {
        console.error('Failed to load job', err);
        toast({
          title: 'Error',
          description: 'Failed to load job details.',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };
    fetchJob();
  }, [id, toast]);

  if (loading) {
    return (
      <CandidateLayout>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin" />
          <p className="ml-2">Loading job...</p>
        </div>
      </CandidateLayout>
    );
  }

  if (!job) {
    return (
      <CandidateLayout>
        <div className="text-center py-20 space-y-4">
          <p className="text-muted-foreground">Job not found.</p>
          <Button asChild>
            <Link href="/candidate/job">Browse Jobs</Link>
          </Button>
        </div>
      </CandidateLayout>
    );
  }

  return (
    <CandidateLayout>
      <div className="space-y-6 max-w-5xl mx-auto">
        <div>
          <Button variant="ghost" size="sm" asChild className="mb-4">
            <Link href="/candidate/job">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Jobs
            </Link>
          </Button>

          <div className="flex flex-col md:flex-row md:items-start md:justify-between gap-4">
            <div className="flex items-start gap-4">
              <div className="p-3 bg-primary/10 rounded-lg">
                <Building2 className="w-8 h-8 text-primary" />
              </div>
              <div>
                <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
                  {job.title}
                </h1>
                <p className="text-muted-foreground mt-1">
                  {job.company_name || 'Company'}
                </p>
                <div className="flex flex-wrap gap-3 mt-3 text-sm text-muted-foreground">
                  <span className="flex items-center gap-1.5">
                    <MapPin className="w-4 h-4" />
                    {job.location}
                  </span>
                  <span className="flex items-center gap-1.5">
                    <Briefcase className="w-4 h-4" />
                    {job.experience_level}
                  </span>
                  {job.salary_min && job.salary_max && (
                    <span className="flex items-center gap-1.5">
                      <DollarSign className="w-4 h-4" />
                      ${job.salary_min.toLocaleString()} - ${job.salary_max.toLocaleString()}
                    </span>
                  )}
                  {job.last_date_to_apply && (
                    <span className="flex items-center gap-1.5">
                      <Calendar className="w-4 h-4" />
                      Apply by {format(new Date(job.last_date_to_apply), 'MMM d, yyyy')}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="flex flex-col items-end gap-2 shrink-0">
              <Badge variant="secondary">{job.type}</Badge>
              {hasApplied ? (
                <Button disabled size="lg" variant="secondary">
                  Applied
                </Button>
              ) : (
                <Button size="lg" onClick={() => setIsApplyOpen(true)}>
                  Apply Now
                </Button>
              )}
            </div>
          </div>
        </div>

        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Job Description</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="whitespace-pre-wrap text-muted-foreground leading-relaxed">
              {job.description}
            </p>
          </CardContent>
        </Card>

        {job.required_skills && job.required_skills.length > 0 && (
          <Card className="bg-card border-border">
            <CardHeader>
              <CardTitle>Required Skills</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-wrap gap-2">
                {job.required_skills.map((skill) => (
                  <Badge key={skill} variant="secondary">
                    {skill}
                  </Badge>
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      <ApplyJobModal
        jobId={job.id}
        jobTitle={job.title}
        applicationQuestions={job.application_questions || []}
        isOpen={isApplyOpen}
        onClose={() => setIsApplyOpen(false)}
        onApplySuccess={() => setHasApplied(true)}
      />
    </CandidateLayout>
  );
}
