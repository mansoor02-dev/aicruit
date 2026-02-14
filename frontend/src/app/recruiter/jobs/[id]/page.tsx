'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { 
  ArrowLeft, 
  MapPin, 
  Briefcase, 
  DollarSign, 
  Calendar as CalendarIcon,
  FileText,
  Edit,
  XCircle,
  Download,
  Loader2
} from 'lucide-react';
import { format } from 'date-fns';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { api } from '@/lib/api';

interface ApplicantInfo {
  application_id: string;
  application_status: string;
  ai_match_score: number;
  applied_at: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  candidate_phone: string;
  candidate_linkedin: string | null;
  resume_id: string;
  resume_url: string;
}

interface JobDetail {
  id: string;
  title: string;
  description: string;
  location: string;
  type: string;
  salary_min: number | null;
  salary_max: number | null;
  required_skills?: string[];
  experience_level: string;
  company_id: string;
  recruiter_id: string;
  status: string;
  created_at: string;
  last_date_to_apply?: string | null;
  applicants?: ApplicantInfo[];
}

const statusColumns = ['APPLIED', 'SCREENING', 'INTERVIEW_SCHEDULED', 'OFFERED', 'REJECTED'];
const statusLabels: Record<string, string> = {
  'APPLIED': 'Applied',
  'SCREENING': 'Screening',
  'INTERVIEW_SCHEDULED': 'Interview Scheduled',
  'OFFERED': 'Offered',
  'REJECTED': 'Rejected'
};

const statusColors: Record<string, string> = {
  'APPLIED': 'bg-gray-500/20 text-gray-500 border-gray-500/30',
  'SCREENING': 'bg-blue-500/20 text-blue-500 border-blue-500/30',
  'INTERVIEW_SCHEDULED': 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
  'OFFERED': 'bg-green-500/20 text-green-500 border-green-500/30',
  'REJECTED': 'bg-red-500/20 text-red-500 border-red-500/30'
};

export default function JobDetails() {
  const params = useParams();
  const id = params.id as string;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [selectedApplicant, setSelectedApplicant] = useState<ApplicantInfo | null>(null);
  const [interviewDate, setInterviewDate] = useState<Date>();
  const [interviewTime, setInterviewTime] = useState('');
  const { toast } = useToast();

  const safeFormatDate = (value?: string | null) => {
    if (!value) return '—';
    const d = new Date(value);
    return isNaN(d.getTime()) ? '—' : format(d, 'MMM d, yyyy');
  };

  useEffect(() => {
    const fetchJobDetails = async () => {
      try {
        setLoading(true);
        const response: JobDetail = await api.get(`/jobs/${id}`);
        setJob(response);
      } catch (error) {
        console.error('Failed to fetch job details:', error);
        toast({
          title: 'Error',
          description: 'Failed to load job details. Please try again.',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchJobDetails();
  }, [id, toast]);

  if (loading) {
    return (
      <RecruiterLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      </RecruiterLayout>
    );
  }

  if (!job) {
    return (
      <RecruiterLayout>
        <div className="text-center py-12">
          <p className="text-muted-foreground">Job not found</p>
          <Button asChild className="mt-4">
            <Link href="/recruiter/jobs">Back to Jobs</Link>
          </Button>
        </div>
      </RecruiterLayout>
    );
  }

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-green-500';
    if (score >= 70) return 'text-yellow-500';
    return 'text-destructive';
  };

  // Safe derived values to avoid undefined errors
  const applicants = job?.applicants ?? [];
  const requiredSkills = job?.required_skills ?? [];

  const handleScheduleInterview = () => {
    if (!interviewDate || !interviewTime) {
      toast({
        title: 'Error',
        description: 'Please select both date and time',
        variant: 'destructive',
      });
      return;
    }

    toast({
      title: 'Success',
      description: `Interview scheduled for ${selectedApplicant?.candidate_name}`,
    });
    
    setSelectedApplicant(null);
    setInterviewDate(undefined);
    setInterviewTime('');
  };

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/recruiter/jobs">
              <ArrowLeft className="w-5 h-5" />
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-2xl font-bold text-foreground">{job.title}</h1>
            <div className="flex items-center gap-4 mt-1 text-muted-foreground flex-wrap">
              <span className="flex items-center gap-1">
                <MapPin className="w-4 h-4" />
                {job.location}
              </span>
              <span className="flex items-center gap-1">
                <Briefcase className="w-4 h-4" />
                {job.type}
              </span>
              <span className="flex items-center gap-1">
                <DollarSign className="w-4 h-4" />
                {job.salary_min ? `$${job.salary_min.toLocaleString()}` : 'N/A'} - {job.salary_max ? `$${job.salary_max.toLocaleString()}` : 'N/A'}
              </span>
            </div>
          </div>
          <Button variant="outline">
            <Edit className="w-4 h-4 mr-2" />
            Edit
          </Button>
          <Button variant="destructive">
            <XCircle className="w-4 h-4 mr-2" />
            Close Job
          </Button>
        </div>

        {/* Job Info */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="text-lg">Job Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="prose prose-invert max-w-none">
              <p className="text-foreground whitespace-pre-wrap">{job.description}</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">Experience Level</p>
                <p className="font-medium">{job.experience_level}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Posted</p>
                <p className="font-medium">{safeFormatDate(job.created_at)}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Applicants</p>
                <p className="font-medium">{applicants.length}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Status</p>
                <Badge className="bg-green-500/20 text-green-500 border-green-500/30">{job.status}</Badge>
              </div>
            </div>
            {requiredSkills.length > 0 && (
              <div>
                <p className="text-sm text-muted-foreground mb-2">Required Skills</p>
                <div className="flex flex-wrap gap-2">
                  {requiredSkills.map((skill) => (
                    <Badge key={skill} variant="secondary">{skill}</Badge>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Applicant Kanban Board */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Applicants by Status</h2>
          <div className="grid grid-cols-5 gap-4 overflow-x-auto">
            {statusColumns.map((status) => {
              const columnApplicants = applicants.filter(a => a.application_status === status);
              return (
                <div key={status} className="space-y-3 min-w-[280px]">
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium text-muted-foreground">{statusLabels[status]}</h3>
                    <Badge variant="outline" className="text-xs">
                      {columnApplicants.length}
                    </Badge>
                  </div>
                  <div className="space-y-3">
                    {columnApplicants.map((applicant) => (
                      <Card key={applicant.application_id} className="bg-card border-border">
                        <CardContent className="p-4">
                          <p className="font-medium text-foreground">{applicant.candidate_name}</p>
                          <p className="text-xs text-muted-foreground mt-1">{applicant.candidate_email}</p>
                          <div className="flex items-center justify-between mt-3">
                            <span className={cn("text-sm font-medium", getScoreColor(applicant.ai_match_score))}>
                              {applicant.ai_match_score}% Match
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-3">
                            <Button 
                              variant="ghost" 
                              size="sm" 
                              className="w-full text-xs"
                              asChild
                            >
                              <a href={applicant.resume_url} target="_blank" rel="noopener noreferrer">
                                <Download className="w-3 h-3 mr-1" />
                                Resume
                              </a>
                            </Button>
                          </div>
                          {status === 'SCREENING' && (
                            <Dialog>
                              <DialogTrigger asChild>
                                <Button 
                                  size="sm" 
                                  className="w-full mt-2 text-xs"
                                  onClick={() => setSelectedApplicant(applicant)}
                                >
                                  <CalendarIcon className="w-3 h-3 mr-1" />
                                  Schedule
                                </Button>
                              </DialogTrigger>
                              <DialogContent className="bg-card">
                                <DialogHeader>
                                  <DialogTitle>Schedule Interview</DialogTitle>
                                </DialogHeader>
                                <div className="space-y-4 py-4">
                                  <p className="text-muted-foreground">
                                    Schedule an interview with {applicant.candidate_name}
                                  </p>
                                  <div className="space-y-2">
                                    <Label>Date</Label>
                                    <Popover>
                                      <PopoverTrigger asChild>
                                        <Button variant="outline" className="w-full justify-start">
                                          <CalendarIcon className="w-4 h-4 mr-2" />
                                          {interviewDate ? format(interviewDate, 'PPP') : 'Pick a date'}
                                        </Button>
                                      </PopoverTrigger>
                                      <PopoverContent className="w-auto p-0 bg-popover" align="start">
                                        <Calendar
                                          mode="single"
                                          selected={interviewDate}
                                          onSelect={setInterviewDate}
                                          disabled={(date) => date < new Date()}
                                          className="pointer-events-auto"
                                        />
                                      </PopoverContent>
                                    </Popover>
                                  </div>
                                  <div className="space-y-2">
                                    <Label htmlFor="time">Time</Label>
                                    <Input
                                      id="time"
                                      type="time"
                                      value={interviewTime}
                                      onChange={(e) => setInterviewTime(e.target.value)}
                                      className="bg-background"
                                    />
                                  </div>
                                  <Button onClick={handleScheduleInterview} className="w-full">
                                    Confirm Interview
                                  </Button>
                                </div>
                              </DialogContent>
                            </Dialog>
                          )}
                        </CardContent>
                      </Card>
                    ))}
                    {columnApplicants.length === 0 && (
                      <div className="p-4 text-center text-sm text-muted-foreground border border-dashed border-border rounded-lg">
                        No applicants
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </RecruiterLayout>
  );
}

