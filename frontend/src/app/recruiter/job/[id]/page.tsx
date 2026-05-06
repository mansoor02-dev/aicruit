'use client';

import { useState, useEffect } from 'react';
import { useParams, useRouter } from 'next/navigation';
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
  Edit,
  Settings,
  XCircle,
  Loader2
} from 'lucide-react';
import { format } from 'date-fns';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { api, emailApi } from '@/lib/api';
import { KanbanBoard } from '@/components/kanban/KanbanBoard';
import { Switch } from '@/components/ui/switch';
import { Sparkles, Mail } from 'lucide-react';

interface ApplicantInfo {
  application_id: string;
  application_status: string;
  applied_at: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  candidate_phone: string;
  candidate_linkedin: string | null;
  resume_id: string;
  resume_url: string;
}

interface JobUpdateData {
  title: string;
  description: string;
  location: string;
  type: string;
  experience_level: string;
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

export default function JobDetails() {
  const params = useParams();
  const id = params.id as string;
  const [job, setJob] = useState<JobDetail | null>(null);
  const [aiInterviewEnabled, setAiInterviewEnabled] = useState<boolean>(false);
  const [loading, setLoading] = useState(true);
  const [selectedApplicant, setSelectedApplicant] = useState<ApplicantInfo | null>(null);
  const [interviewDate, setInterviewDate] = useState<Date>();
  const [interviewTime, setInterviewTime] = useState('');
  const [scheduleSendEmail, setScheduleSendEmail] = useState(false);
  const [scheduleEmailSubject, setScheduleEmailSubject] = useState('');
  const [scheduleEmailBody, setScheduleEmailBody] = useState('');
  const [scheduleEmailDrafting, setScheduleEmailDrafting] = useState(false);
  
  const [isEditing, setIsEditing] = useState(false);
  const [editForm, setEditForm] = useState<JobUpdateData>({
    title: '', description: '', location: '', type: '', experience_level: ''
  });
  
  const { toast } = useToast();
  const router = useRouter();

  const safeFormatDate = (value?: string | null) => {
    if (!value) return 'â€”';
    const d = new Date(value);
    return isNaN(d.getTime()) ? 'â€”' : format(d, 'MMM d, yyyy');
  };

  useEffect(() => {
    const fetchJobDetails = async () => {
      try {
        setLoading(true);
        const response: JobDetail = await api.get(`/job/${id}`);
        setJob(response);
        setEditForm({
          title: response.title,
          description: response.description,
          location: response.location,
          type: response.type,
          experience_level: response.experience_level
        });
        try {
          const settings: { ai_interview_enabled?: boolean } = await api.get(`/job/${id}/interview-settings`);
          setAiInterviewEnabled(Boolean(settings?.ai_interview_enabled));
        } catch {
          setAiInterviewEnabled(false);
        }
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
          <p className="text-muted-foreground mt-1">Job not found</p>
          <Button asChild className="mt-4">
            <Link href="/recruiter/job">Back to Jobs</Link>
          </Button>
        </div>
      </RecruiterLayout>
    );
  }

  // Safe derived values to avoid undefined errors
  const applicants = job?.applicants ?? [];
  const requiredSkills = job?.required_skills ?? [];

  const handleScheduleInterview = async () => {
    if (!selectedApplicant || !interviewDate || !interviewTime) {
      toast({
        title: 'Error',
        description: 'Please select both date and time',
        variant: 'destructive',
      });
      return;
    }

    try {
      const [hours, minutes] = interviewTime.split(':').map(Number);
      const scheduledAt = new Date(interviewDate);
      scheduledAt.setHours(hours, minutes, 0, 0);

      // Manually build ISO string in local time to avoid UTC shift losing the time
      const pad = (n: number) => n.toString().padStart(2, '0');
      const isoString = `${scheduledAt.getFullYear()}-${pad(scheduledAt.getMonth() + 1)}-${pad(scheduledAt.getDate())}T${pad(hours)}:${pad(minutes)}:00`;

      await api.post('/interview/schedule', {
        application_id: selectedApplicant.application_id,
        scheduled_at: isoString,
        send_email: scheduleSendEmail,
        email_subject: scheduleSendEmail ? scheduleEmailSubject : null,
        email_body: scheduleSendEmail ? scheduleEmailBody : null,
      });

      toast({
        title: 'Success',
        description: `Interview scheduled for ${selectedApplicant.candidate_name}`,
      });

      // Update local state to reflect the new status if needed
      if (job && job.applicants) {
        setJob({
          ...job,
          applicants: job.applicants.map(app => 
            app.application_id === selectedApplicant.application_id
              ? { ...app, application_status: 'INTERVIEW_SCHEDULED' }
              : app
          )
        });
      }

    } catch (error) {
      console.error('Failed to schedule interview:', error);
      toast({
        title: 'Error',
        description: 'Failed to schedule interview. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setSelectedApplicant(null);
      setInterviewDate(undefined);
      setInterviewTime('');
      setScheduleSendEmail(false);
      setScheduleEmailSubject('');
      setScheduleEmailBody('');
    }
  };

  const handleGenerateScheduleEmail = async () => {
    if (!selectedApplicant) return;
    setScheduleEmailDrafting(true);
    try {
      const res = await emailApi.draft({
        scenario: 'interview_scheduled',
        application_id: selectedApplicant.application_id,
      });
      setScheduleEmailSubject(res.subject);
      setScheduleEmailBody(res.body);
    } catch (err) {
      toast({
        title: 'Error',
        description: 'Failed to generate email draft.',
        variant: 'destructive',
      });
    } finally {
      setScheduleEmailDrafting(false);
    }
  };

  const handleCloseJob = async () => {
    if (!window.confirm("Are you sure you want to close and delete this job?")) return;
    try {
      await api.delete(`/job/${id}`);
      toast({ title: 'Success', description: 'Job closed successfully.' });
      router.push('/recruiter/job');
    } catch (error) {
      toast({ title: 'Error', description: 'Failed to close job.', variant: 'destructive' });
    }
  };

  const handleEditSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      // You should hit a PUT endpoint that updates job data
      const response: JobDetail = await api.put(`/job/${id}`, editForm);
      setJob({ ...job, ...response });
      setIsEditing(false);
      toast({ title: 'Success', description: 'Job updated.' });
    } catch (error) {
      toast({ title: 'Error', description: 'Failed to update job.', variant: 'destructive' });
    }
  };

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" asChild>
            <Link href="/recruiter/job">
              <ArrowLeft className="w-5 h-5" />
            </Link>
          </Button>
          <div className="flex-1">
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">{job.title}</h1>
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
          <Button variant="outline" asChild>
            <Link href={`/recruiter/job/${id}/interview-settings`}>
              <Settings className="w-4 h-4 mr-2" />
              Interview Settings
            </Link>
          </Button>
          <Button variant="outline" onClick={() => setIsEditing(true)}>
            <Edit className="w-4 h-4 mr-2" />
            Edit
          </Button>
          <Button variant="destructive" onClick={handleCloseJob}>
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
                <Badge className="bg-success/15 text-success border-success/25">{job.status}</Badge>
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

        {/* Applicants Kanban Board */}
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold">Applicants</h2>
            <Button
              variant="outline"
              onClick={() => router.push(`/recruiter/job/${id}/email`)}
            >
              <Mail className="w-4 h-4 mr-2" />
              Send Email to Candidates
            </Button>
          </div>
          <KanbanBoard jobId={String(id)} aiInterviewEnabled={aiInterviewEnabled} />
        </div>

        {/* Schedule Interview Dialog */}
        <Dialog open={!!selectedApplicant} onOpenChange={(open) => !open && setSelectedApplicant(null)}>
          <DialogContent className="bg-card sm:max-w-[560px] max-h-[90vh] overflow-y-auto">
            <DialogHeader>
              <DialogTitle>Schedule Interview</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <p className="text-muted-foreground">
                Schedule an interview with <span className="font-medium text-foreground">{selectedApplicant?.candidate_name}</span>
              </p>
              
              <div className="grid gap-4 py-4">
                <div className="grid gap-2">
                  <Label>Date</Label>
                  <Popover>
                    <PopoverTrigger asChild>
                      <Button
                        variant={"outline"}
                        className={cn(
                          "w-full justify-start text-left font-normal",
                          !interviewDate && "text-muted-foreground"
                        )}
                      >
                        <CalendarIcon className="mr-2 h-4 w-4" />
                        {interviewDate ? format(interviewDate, "PPP") : <span>Pick a date</span>}
                      </Button>
                    </PopoverTrigger>
                    <PopoverContent className="w-auto p-0" align="start">
                      <Calendar
                        mode="single"
                        selected={interviewDate}
                        onSelect={setInterviewDate}
                        disabled={(date) => {
                          const today = new Date();
                          today.setHours(0, 0, 0, 0);
                          return date < today;
                        }}
                        initialFocus
                      />
                    </PopoverContent>
                  </Popover>
                </div>
                <div className="grid gap-2">
                  <Label htmlFor="time">Time</Label>
                  <Input
                    id="time"
                    type="time"
                    value={interviewTime}
                    onChange={(e) => setInterviewTime(e.target.value)}
                    className="col-span-3"
                  />
                </div>
              </div>

              <div className="flex items-center justify-between rounded-md border p-3">
                <div className="space-y-0.5">
                  <Label className="text-sm font-medium">Send email notification to candidate</Label>
                  <p className="text-xs text-muted-foreground">
                    Notify the candidate by email when scheduling.
                  </p>
                </div>
                <Switch
                  checked={scheduleSendEmail}
                  onCheckedChange={setScheduleSendEmail}
                />
              </div>

              {scheduleSendEmail && (
                <div className="grid gap-3">
                  <div className="grid gap-2">
                    <Label htmlFor="email-subject">Subject</Label>
                    <Input
                      id="email-subject"
                      value={scheduleEmailSubject}
                      onChange={(e) => setScheduleEmailSubject(e.target.value)}
                      placeholder="Interview scheduled for {job_title}"
                    />
                  </div>
                  <div className="grid gap-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="email-body">Body</Label>
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={handleGenerateScheduleEmail}
                        disabled={scheduleEmailDrafting}
                      >
                        {scheduleEmailDrafting ? (
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        ) : (
                          <Sparkles className="w-4 h-4 mr-2" />
                        )}
                        Generate with AI
                      </Button>
                    </div>
                    <textarea
                      id="email-body"
                      className="flex min-h-[160px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      value={scheduleEmailBody}
                      onChange={(e) => setScheduleEmailBody(e.target.value)}
                      placeholder="Write the email body or click Generate with AI..."
                    />
                  </div>
                </div>
              )}

              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={() => setSelectedApplicant(null)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleScheduleInterview}
                  disabled={
                    !interviewDate ||
                    !interviewTime ||
                    (scheduleSendEmail && (!scheduleEmailSubject || !scheduleEmailBody))
                  }
                >
                  Confirm Schedule
                </Button>
              </div>
            </div>
          </DialogContent>
        </Dialog>

        {/* Edit Job Dialog */}
        <Dialog open={isEditing} onOpenChange={setIsEditing}>
          <DialogContent className="bg-card sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>Edit Job Details</DialogTitle>
            </DialogHeader>
            <form onSubmit={handleEditSubmit} className="space-y-4 py-4">
              <div className="grid gap-2">
                <Label htmlFor="title">Title</Label>
                <Input
                  id="title"
                  value={editForm.title}
                  onChange={(e) => setEditForm({...editForm, title: e.target.value})}
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="description">Description</Label>
                <textarea
                  id="description"
                  className="flex min-h-[80px] w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  value={editForm.description}
                  onChange={(e) => setEditForm({...editForm, description: e.target.value})}
                  required
                />
              </div>
              <div className="grid gap-2">
                <Label htmlFor="location">Location</Label>
                <Input
                  id="location"
                  value={editForm.location}
                  onChange={(e) => setEditForm({...editForm, location: e.target.value})}
                  required
                />
              </div>
              <div className="grid grid-cols-2 gap-4">
                  <div className="grid gap-2">
                    <Label htmlFor="type">Type</Label>
                    <Input
                      id="type"
                      value={editForm.type}
                      onChange={(e) => setEditForm({...editForm, type: e.target.value})}
                      required
                    />
                  </div>
                  <div className="grid gap-2">
                    <Label htmlFor="experience">Experience</Label>
                    <Input
                      id="experience"
                      value={editForm.experience_level}
                      onChange={(e) => setEditForm({...editForm, experience_level: e.target.value})}
                      required
                    />
                  </div>
              </div>
              <div className="flex justify-end gap-3 pt-4">
                <Button type="button" variant="outline" onClick={() => setIsEditing(false)}>
                  Cancel
                </Button>
                <Button type="submit">
                  Save Changes
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>
    </RecruiterLayout>
  );
}

