'use client';

import { useState, useEffect } from 'react';
import { useParams } from 'next/navigation';
import Link from 'next/link';
import { CandidateLayout } from '@/components/layout/CandidateLayout';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Building2, 
  MapPin, 
  Calendar,
  Briefcase,
  DollarSign,
  ArrowLeft,
  Loader2,
  Clock,
  Video
} from 'lucide-react';
import { format } from 'date-fns';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { Application } from '../page';

export default function ApplicationDetails() {
  const params = useParams();
  const id = params.id as string;
  const [application, setApplication] = useState<Application | null>(null);
  const [loading, setLoading] = useState(true);
  const [canStartInterview, setCanStartInterview] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    const fetchApplication = async () => {
      try {
        setLoading(true);
        // Note: Ideally backend should have a single application endpoint, 
        // but for now we fetch all and find the one we need.
        const response: Application[] = await api.get('/job/my-applications');
        const found = response.find(app => app.application_id === id);
        
        if (found) {
          setApplication(found);
        } else {
          toast({
            title: 'Error',
            description: 'Application not found',
            variant: 'destructive',
          });
        }
      } catch (error) {
        console.error('Failed to fetch application details:', error);
        toast({
          title: 'Error',
          description: 'Failed to load application details. Please try again.',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };

    if (id) {
      fetchApplication();
    }
  }, [id, toast]);

  useEffect(() => {
    if (!application?.scheduled_at) {
      setCanStartInterview(false);
      return;
    }

    const checkTime = () => {
      const now = new Date();
      const scheduled = new Date(application.scheduled_at!);
      // Window: scheduled_time <= now <= scheduled_time + 1 hour
      const windowEnd = new Date(scheduled.getTime() + 60 * 60 * 1000); 

      const isTime = now >= scheduled && now <= windowEnd;
      setCanStartInterview(isTime);
    };

    checkTime(); // Check immediately
    const interval = setInterval(checkTime, 1000 * 30); // Check every 30 seconds

    return () => clearInterval(interval);
  }, [application]);

  const handleStartInterview = () => {
    // Open interview page in a new tab
    window.open(`/candidate/interview/${application?.application_id}`, '_blank');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPLIED':
        return <Badge variant="outline">Applied</Badge>;
      case 'SCREENING':
        return <Badge className="bg-blue-500/20 text-blue-500 border-blue-500/30">Under Review</Badge>;
      case 'INTERVIEW_SCHEDULED':
        return <Badge className="bg-yellow-500/20 text-yellow-500 border-yellow-500/30">Interview Scheduled</Badge>;
      case 'OFFERED':
        return <Badge className="bg-green-500/20 text-green-500 border-green-500/30">Offered</Badge>;
      case 'REJECTED':
        return <Badge variant="destructive">Not Selected</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  if (loading) {
    return (
      <CandidateLayout>
        <div className="flex items-center justify-center py-12">
          <Loader2 className="w-6 h-6 animate-spin" />
          <p className="ml-2">Loading application details...</p>
        </div>
      </CandidateLayout>
    );
  }

  if (!application) {
    return (
      <CandidateLayout>
        <div className="text-center py-12">
          <p className="text-muted-foreground mb-4">Application not found</p>
          <Button asChild>
            <Link href="/candidate/applications">Back to Applications</Link>
          </Button>
        </div>
      </CandidateLayout>
    );
  }

  return (
    <CandidateLayout>
      <div className="space-y-6">
        {/* Header / Navigate Back */}
        <div>
          <Button variant="ghost" size="sm" asChild className="mb-4">
            <Link href="/candidate/applications">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Applications
            </Link>
          </Button>
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-2xl font-bold text-foreground">{application.job_title}</h1>
              <div className="flex items-center gap-2 mt-2">
                <Building2 className="w-4 h-4 text-muted-foreground" />
                <span className="text-muted-foreground">AIcruit Company</span>
                <span className="text-muted-foreground">•</span>
                <span className="text-muted-foreground">{application.location}</span>
                <span className="text-muted-foreground">•</span>
                <span className="text-muted-foreground">Applied {format(new Date(application.applied_at), 'MMM d, yyyy')}</span>
              </div>
            </div>
            <div className="flex items-center gap-3">
              {getStatusBadge(application.application_status)}
            </div>
          </div>
        </div>

        {/* Interview Section - Only if scheduled */}
        {(application.application_status === 'INTERVIEW_SCHEDULED' || application.scheduled_at) && (
          <Card className="bg-primary/5 border-primary/20">
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-primary">
                <Video className="w-5 h-5" />
                Interview Scheduled
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                <div className="space-y-1">
                  <p className="text-sm text-muted-foreground">Date & Time</p>
                  <p className="text-lg font-semibold flex items-center gap-2">
                    <Calendar className="w-4 h-4" />
                    {application.scheduled_at 
                      ? format(new Date(application.scheduled_at), 'PPPPp') 
                      : 'Date to be confirmed'}
                  </p>
                   <p className="text-xs text-muted-foreground mt-1">
                      Check-in allowed within 1 hour of scheduled time.
                   </p>
                </div>
                
                <Button 
                  size="lg" 
                  onClick={handleStartInterview}
                >
                  <Video className="w-4 h-4 mr-2" />
                  Join Interview
                </Button>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Job Details */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <div className="md:col-span-2 space-y-6">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Job Description</CardTitle>
              </CardHeader>
              <CardContent>
                <p className="whitespace-pre-wrap text-muted-foreground">
                  {application.job_description}
                </p>
              </CardContent>
            </Card>

            {application.required_skills && application.required_skills.length > 0 && (
              <Card className="bg-card border-border">
                <CardHeader>
                  <CardTitle>Required Skills</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-2">
                    {application.required_skills.map((skill) => (
                      <Badge key={skill} variant="secondary">
                        {skill}
                      </Badge>
                    ))}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>

          <div className="space-y-6">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Job Overview
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="flex items-center gap-3">
                  <Briefcase className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">Job Type</p>
                    <p className="text-sm text-muted-foreground">{application.job_type}</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <DollarSign className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">Salary Range</p>
                    <p className="text-sm text-muted-foreground">
                      {application.salary_min && application.salary_max 
                        ? `$${application.salary_min.toLocaleString()} - $${application.salary_max.toLocaleString()}` 
                        : 'Not specified'}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <Clock className="w-4 h-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">Experience Level</p>
                    <p className="text-sm text-muted-foreground">{application.experience_level}</p>
                  </div>
                </div>
              </CardContent>
            </Card>    
          </div>
        </div>
      </div>
    </CandidateLayout>
  );
}
