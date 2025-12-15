'use client';

import { CandidateLayout } from '@/components/layout/CandidateLayout';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { mockJobs } from '@/data/mockData';
import { 
  Building2, 
  MapPin, 
  Calendar,
  ExternalLink
} from 'lucide-react';
import { format } from 'date-fns';
import Link from 'next/link';

// Mock applications for the candidate
const mockApplications = [
  {
    id: '1',
    jobId: '1',
    status: 'Interview',
    appliedAt: '2024-01-16',
    interviewDate: '2024-01-22T10:00:00',
  },
  {
    id: '2',
    jobId: '2',
    status: 'Under Review',
    appliedAt: '2024-01-14',
  },
  {
    id: '3',
    jobId: '3',
    status: 'Applied',
    appliedAt: '2024-01-18',
  },
];

export default function Applications() {
  const applicationsWithJobs = mockApplications.map(app => ({
    ...app,
    job: mockJobs.find(j => j.id === app.jobId),
  }));

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Applied':
        return <Badge variant="outline">Applied</Badge>;
      case 'Under Review':
        return <Badge className="bg-blue-500/20 text-blue-500 border-blue-500/30">Under Review</Badge>;
      case 'Interview':
        return <Badge className="bg-yellow-500/20 text-yellow-500 border-yellow-500/30">Interview Scheduled</Badge>;
      case 'Offered':
        return <Badge className="bg-green-500/20 text-green-500 border-green-500/30">Offered</Badge>;
      case 'Rejected':
        return <Badge variant="destructive">Not Selected</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  return (
    <CandidateLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">My Applications</h1>
          <p className="text-muted-foreground">Track the status of your job applications</p>
        </div>

        <div className="space-y-4">
          {applicationsWithJobs.map((application) => (
            <Card key={application.id} className="bg-card border-border">
              <CardContent className="p-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
                  <div className="flex items-start gap-4">
                    <div className="p-3 bg-primary/10 rounded-lg">
                      <Building2 className="w-6 h-6 text-primary" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-foreground">
                        {application.job?.title}
                      </h3>
                      <p className="text-muted-foreground">{application.job?.company}</p>
                      <div className="flex items-center gap-4 mt-2 text-sm text-muted-foreground">
                        <span className="flex items-center gap-1">
                          <MapPin className="w-4 h-4" />
                          {application.job?.location}
                        </span>
                        <span className="flex items-center gap-1">
                          <Calendar className="w-4 h-4" />
                          Applied {format(new Date(application.appliedAt), 'MMM d, yyyy')}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-col items-end gap-3">
                    {getStatusBadge(application.status)}
                    {application.status === 'Interview' && application.interviewDate && (
                      <p className="text-sm text-primary font-medium">
                        Interview: {format(new Date(application.interviewDate), 'MMM d, h:mm a')}
                      </p>
                    )}
                    <Button variant="outline" size="sm">
                      View Details
                      <ExternalLink className="w-4 h-4 ml-2" />
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>

        {applicationsWithJobs.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">You haven't applied to any jobs yet</p>
            <Button className="mt-4" asChild>
              <Link href="/candidate/jobs">Browse Jobs</Link>
            </Button>
          </div>
        )}
      </div>
    </CandidateLayout>
  );
}

