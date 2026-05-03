'use client';

import { useState, useEffect } from 'react';
import { CandidateLayout } from '@/components/layout/CandidateLayout';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { 
  Building2, 
  MapPin, 
  Calendar,
  ExternalLink,
  Loader2
} from 'lucide-react';
import { format } from 'date-fns';
import Link from 'next/link';
import { api } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

export interface Application {
  application_id: string;
  application_status: string;
  applied_at: string;
  job_id: string;
  job_title: string;
  job_description: string;
  location: string;
  job_type: string;
  salary_min: number;
  salary_max: number;
  required_skills: string[];
  experience_level: string;
  last_date_to_apply: string | null;
  job_status: string;
  job_created_at: string;
  scheduled_at?: string;
}

export default function Applications() {
  const [applications, setApplications] = useState<Application[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const { toast } = useToast();

  useEffect(() => {
    setMounted(true);
  }, []);

  useEffect(() => {
    if (!mounted) return;

    const fetchApplications = async () => {
      try {
        setLoading(true);
        const response: Application[] = await api.get('/job/my-applications');
        setApplications(response);
      } catch (error) {
        console.error('Failed to fetch applications:', error);
        toast({
          title: 'Error',
          description: 'Failed to load applications. Please try again.',
          variant: 'destructive',
        });
      } finally {
        setLoading(false);
      }
    };

    fetchApplications();
  }, [mounted, toast]);

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPLIED':
        return <Badge variant="outline">Applied</Badge>;
      case 'SCREENING':
        return <Badge className="bg-primary/15 text-primary border-primary/25">Under Review</Badge>;
      case 'INTERVIEW_SCHEDULED':
        return <Badge className="bg-warning/20 text-warning-foreground border-warning/30">Interview Scheduled</Badge>;
      case 'OFFERED':
        return <Badge className="bg-success/15 text-success border-success/25">Offered</Badge>;
      case 'REJECTED':
        return <Badge variant="destructive">Not Selected</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  if (!mounted) {
    return (
      <div className="min-h-screen bg-background p-4">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">My Applications</h1>
            <p className="text-muted-foreground mt-1">Track the status of your job applications</p>
          </div>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin" />
            <p className="ml-2">Loading...</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <CandidateLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">My Applications</h1>
          <p className="text-muted-foreground mt-1">Track the status of your job applications</p>
        </div>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin" />
            <p className="ml-2">Loading applications...</p>
          </div>
        ) : applications.length === 0 ? (
          <div className="text-center py-12">
            <p className="text-muted-foreground mb-4">You haven&apos;t applied to any jobs yet</p>
            <Button asChild>
              <Link href="/candidate/job">Browse Jobs</Link>
            </Button>
          </div>
        ) : (
          <div className="space-y-4">
            {applications.map((application) => (
              <Card key={application.application_id} className="bg-card border-border hover:shadow-lg transition-all">
                <CardContent className="p-6">
                  <div className="flex flex-col md:flex-row md:items-start justify-between gap-4">
                    <div className="flex items-start gap-4 flex-1">
                      <div className="p-3 bg-primary/10 rounded-lg flex-shrink-0">
                        <Building2 className="w-6 h-6 text-primary" />
                      </div>
                      <div className="flex-1 min-w-0">
                        <h3 className="text-lg font-semibold text-foreground mb-1">
                          {application.job_title}
                        </h3>
                        <p className="text-sm text-muted-foreground mb-3 line-clamp-2">
                          {application.job_description}
                        </p>
                        
                        <div className="flex flex-wrap gap-4 text-sm text-muted-foreground mb-3">
                          <span className="flex items-center gap-1">
                            <MapPin className="w-4 h-4" />
                            {application.location}
                          </span>
                          <span className="flex items-center gap-1">
                            <Calendar className="w-4 h-4" />
                            Applied {format(new Date(application.applied_at), 'MMM d, yyyy')}
                          </span>
                        </div>

                        <div className="flex flex-wrap gap-2 mb-3">
                          <Badge variant="outline" className="text-xs">
                            {application.job_type}
                          </Badge>
                          <Badge variant="outline" className="text-xs">
                            {application.experience_level}
                          </Badge>
                          {application.salary_min && application.salary_max && (
                            <Badge variant="outline" className="text-xs">
                              ${application.salary_min.toLocaleString()} - ${application.salary_max.toLocaleString()}
                            </Badge>
                          )}
                        </div>

                        {application.required_skills && application.required_skills.length > 0 && (
                          <div className="flex flex-wrap gap-1">
                            {application.required_skills.slice(0, 4).map((skill) => (
                              <Badge key={skill} variant="secondary" className="text-xs">
                                {skill}
                              </Badge>
                            ))}
                            {application.required_skills.length > 4 && (
                              <Badge variant="secondary" className="text-xs">
                                +{application.required_skills.length - 4}
                              </Badge>
                            )}
                          </div>
                        )}
                      </div>
                    </div>

                    <div className="flex flex-col items-end gap-3 flex-shrink-0">
                      {getStatusBadge(application.application_status)}
                      <Button variant="outline" size="sm" asChild>
                        <Link href={`/candidate/applications/${application.application_id}`}>
                          View Details
                          <ExternalLink className="w-4 h-4 ml-2" />
                        </Link>
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </CandidateLayout>
  );
}


