'use client';

import { useState } from 'react';
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
import { mockJobs, mockApplicants, Applicant } from '@/data/mockData';
import { 
  ArrowLeft, 
  MapPin, 
  Briefcase, 
  DollarSign, 
  Calendar as CalendarIcon,
  FileText,
  Edit,
  XCircle
} from 'lucide-react';
import { format, parseISO } from 'date-fns';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';
import { Calendar } from '@/components/ui/calendar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';

const statusColumns: Applicant['status'][] = ['Applied', 'Screening', 'Interview', 'Offered', 'Rejected'];

export default function JobDetails() {
  const params = useParams();
  const id = params.id as string;
  const job = mockJobs.find(j => j.id === id);
  const [applicants, setApplicants] = useState(mockApplicants.filter(a => a.jobId === id));
  const [selectedApplicant, setSelectedApplicant] = useState<Applicant | null>(null);
  const [interviewDate, setInterviewDate] = useState<Date>();
  const [interviewTime, setInterviewTime] = useState('');
  const { toast } = useToast();

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

  const handleScheduleInterview = () => {
    if (!interviewDate || !interviewTime) {
      toast({
        title: 'Error',
        description: 'Please select both date and time',
        variant: 'destructive',
      });
      return;
    }

    setApplicants(prev => 
      prev.map(a => 
        a.id === selectedApplicant?.id 
          ? { ...a, status: 'Interview' as const } 
          : a
      )
    );

    toast({
      title: 'Success',
      description: `Interview scheduled for ${selectedApplicant?.name}`,
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
            <div className="flex items-center gap-4 mt-1 text-muted-foreground">
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
                ${job.salaryMin.toLocaleString()} - ${job.salaryMax.toLocaleString()}
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
          <CardContent className="p-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div>
                <p className="text-sm text-muted-foreground">Experience Level</p>
                <p className="font-medium">{job.experienceLevel}</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Posted</p>
                <p className="font-medium">{format(parseISO(job.createdAt), 'MMM d, yyyy')}</p>
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
            <div className="flex flex-wrap gap-2">
              {job.requiredSkills.map((skill) => (
                <Badge key={skill} variant="secondary">{skill}</Badge>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Applicant Kanban Board */}
        <div>
          <h2 className="text-xl font-semibold mb-4">Applicants</h2>
          <div className="grid grid-cols-5 gap-4">
            {statusColumns.map((status) => {
              const columnApplicants = applicants.filter(a => a.status === status);
              return (
                <div key={status} className="space-y-3">
                  <div className="flex items-center justify-between">
                    <h3 className="font-medium text-muted-foreground">{status}</h3>
                    <Badge variant="outline" className="text-xs">
                      {columnApplicants.length}
                    </Badge>
                  </div>
                  <div className="space-y-3">
                    {columnApplicants.map((applicant) => (
                      <Card key={applicant.id} className="bg-card border-border">
                        <CardContent className="p-4">
                          <p className="font-medium text-foreground">{applicant.name}</p>
                          <div className="flex items-center justify-between mt-2">
                            <span className={cn("text-sm font-medium", getScoreColor(applicant.aiMatchScore))}>
                              {applicant.aiMatchScore}% Match
                            </span>
                          </div>
                          <div className="flex items-center gap-2 mt-3">
                            <Button variant="ghost" size="sm" className="w-full">
                              <FileText className="w-3 h-3 mr-1" />
                              Resume
                            </Button>
                          </div>
                          {status === 'Screening' && (
                            <Dialog>
                              <DialogTrigger asChild>
                                <Button 
                                  size="sm" 
                                  className="w-full mt-2"
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
                                    Schedule an interview with {applicant.name}
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

