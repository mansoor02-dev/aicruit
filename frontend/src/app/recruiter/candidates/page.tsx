'use client';

import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { mockApplicants, mockJobs } from '@/data/mockData';
import { Search, FileText, Mail, Users } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { format, parseISO } from 'date-fns';

export default function Candidates() {
  const [searchTerm, setSearchTerm] = useState('');

  const candidatesWithJobs = mockApplicants.map(applicant => ({
    ...applicant,
    job: mockJobs.find(j => j.id === applicant.jobId),
  }));

  const filteredCandidates = candidatesWithJobs.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.job?.title.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'Applied':
        return <Badge variant="outline">Applied</Badge>;
      case 'Screening':
        return <Badge variant="soft">Screening</Badge>;
      case 'Interview':
        return <Badge variant="warning">Interview</Badge>;
      case 'Offered':
        return <Badge variant="success">Offered</Badge>;
      case 'Rejected':
        return <Badge variant="destructive">Rejected</Badge>;
      default:
        return <Badge variant="secondary">{status}</Badge>;
    }
  };

  const getScoreColor = (score: number) => {
    if (score >= 85) return 'text-success';
    if (score >= 70) return 'text-warning-foreground';
    return 'text-destructive';
  };

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">All Candidates</h1>
            <p className="text-muted-foreground mt-1">View and manage all applicants across your job postings</p>
          </div>
          <Badge variant="soft" className="text-sm py-1.5 px-3">
            <Users className="w-3.5 h-3.5 mr-1.5" />
            {filteredCandidates.length} candidate{filteredCandidates.length === 1 ? '' : 's'}
          </Badge>
        </div>

        <div className="relative max-w-md">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search candidates by name, email, or role..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10"
          />
        </div>

        <Card className="bg-card border-border overflow-hidden">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/40 hover:bg-muted/40">
                  <TableHead>Candidate</TableHead>
                  <TableHead>Applied For</TableHead>
                  <TableHead>AI Match</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Applied Date</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filteredCandidates.length === 0 && (
                  <TableRow>
                    <TableCell colSpan={6} className="py-12 text-center text-muted-foreground">
                      No candidates match your search.
                    </TableCell>
                  </TableRow>
                )}
                {filteredCandidates.map((candidate, idx) => (
                  <TableRow key={candidate.id} className="animate-fade-in-up transition-colors" style={{ animationDelay: `${Math.min(idx * 30, 400)}ms` } as React.CSSProperties}>
                    <TableCell>
                      <div className="flex items-center gap-3">
                        <Avatar className="ring-2 ring-primary/15">
                          <AvatarFallback className="bg-accent text-accent-foreground font-semibold">
                            {candidate.name.split(' ').map(n => n[0]).join('')}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-semibold">{candidate.name}</p>
                          <p className="text-sm text-muted-foreground">{candidate.email}</p>
                        </div>
                      </div>
                    </TableCell>
                    <TableCell className="text-sm">{candidate.job?.title || 'Unknown'}</TableCell>
                    <TableCell>
                      <span className={cn('font-semibold tabular-nums', getScoreColor(candidate.aiMatchScore))}>
                        {candidate.aiMatchScore}%
                      </span>
                    </TableCell>
                    <TableCell>{getStatusBadge(candidate.status)}</TableCell>
                    <TableCell className="text-sm text-muted-foreground">{format(parseISO(candidate.appliedAt), 'MMM d, yyyy')}</TableCell>
                    <TableCell className="text-right">
                      <div className="flex items-center justify-end gap-1">
                        <Button variant="ghost" size="icon" aria-label="View resume">
                          <FileText className="w-4 h-4" />
                        </Button>
                        <Button variant="ghost" size="icon" aria-label="Email candidate">
                          <Mail className="w-4 h-4" />
                        </Button>
                      </div>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </RecruiterLayout>
  );
}