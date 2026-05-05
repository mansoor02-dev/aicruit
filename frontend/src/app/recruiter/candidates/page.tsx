'use client';

import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent } from '@/components/ui/card';
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
import { Search, Users, Loader2 } from 'lucide-react';
import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { cn } from '@/lib/utils';
import { format } from 'date-fns';
import { api } from '@/lib/api';

interface AllCandidateRow {
  application_id: string;
  candidate_id: string;
  name: string;
  email: string;
  phone: string;
  location: string;
  job_id: string;
  job_title: string;
  status: string;
  ai_match_score: number | null;
  interview_id: string | null;
  interview_status: string | null;
  applied_at: string;
}

const STATUS_LABELS: Record<string, string> = {
  APPLIED: 'Applied',
  SCREENING: 'Screening',
  INTERVIEW_SCHEDULED: 'Interview Scheduled',
  INTERVIEW_COMPLETED: 'Interview Completed',
  OFFERED: 'Offered',
  REJECTED: 'Rejected',
};

export default function Candidates() {
  const [searchTerm, setSearchTerm] = useState('');
  const router = useRouter();

  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['all-candidates'],
    queryFn: () => api.get<AllCandidateRow[]>('/job/candidates/all'),
  });

  const candidates = data ?? [];
  const filtered = candidates.filter((c) => {
    const q = searchTerm.toLowerCase();
    return (
      c.name.toLowerCase().includes(q) ||
      c.email.toLowerCase().includes(q) ||
      c.job_title.toLowerCase().includes(q)
    );
  });

  const getStatusBadge = (status: string) => {
    const label = STATUS_LABELS[status] ?? status;
    switch (status) {
      case 'APPLIED':
        return <Badge variant="outline">{label}</Badge>;
      case 'SCREENING':
        return <Badge className="bg-primary/15 text-primary border-primary/25">{label}</Badge>;
      case 'INTERVIEW_SCHEDULED':
        return <Badge className="bg-warning/20 text-warning-foreground border-warning/30">{label}</Badge>;
      case 'INTERVIEW_COMPLETED':
        return <Badge className="bg-indigo-500/20 text-indigo-400 border-indigo-500/30">{label}</Badge>;
      case 'OFFERED':
        return <Badge className="bg-success/15 text-success border-success/25">{label}</Badge>;
      case 'REJECTED':
        return <Badge variant="destructive">{label}</Badge>;
      default:
        return <Badge variant="secondary">{label}</Badge>;
    }
  };

  const getScoreColor = (score: number | null) => {
    if (score == null) return 'text-muted-foreground';
    if (score >= 85) return 'text-success';
    if (score >= 70) return 'text-warning-foreground';
    return 'text-destructive';
  };

  const handleRowClick = (row: AllCandidateRow) => {
    router.push(`/recruiter/job/${row.job_id}/candidate/${row.application_id}`);
  };

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between gap-4 flex-wrap">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">All Candidates</h1>
            <p className="text-muted-foreground mt-1">
              View and manage all applicants across your job postings
            </p>
          </div>
          <Badge variant="soft" className="text-sm py-1.5 px-3">
            <Users className="w-3.5 h-3.5 mr-1.5" />
            {filtered.length} candidate{filtered.length === 1 ? '' : 's'}
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
            {isLoading ? (
              <div className="flex items-center justify-center py-16 text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                Loading candidates...
              </div>
            ) : isError ? (
              <div className="py-12 text-center text-destructive text-sm">
                Failed to load candidates: {error instanceof Error ? error.message : 'Unknown error'}
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/40 hover:bg-muted/40">
                    <TableHead>Candidate</TableHead>
                    <TableHead>Applied For</TableHead>
                    <TableHead>AI Match</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Applied Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {filtered.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="py-12 text-center text-muted-foreground">
                        No candidates match your search.
                      </TableCell>
                    </TableRow>
                  )}
                  {filtered.map((c, idx) => (
                    <TableRow
                      key={c.application_id}
                      onClick={() => handleRowClick(c)}
                      className="cursor-pointer animate-fade-in-up transition-colors hover:bg-muted/40"
                      style={{ animationDelay: `${Math.min(idx * 30, 400)}ms` } as React.CSSProperties}
                    >
                      <TableCell>
                        <div className="flex items-center gap-3">
                          <Avatar className="ring-2 ring-primary/15">
                            <AvatarFallback className="bg-accent text-accent-foreground font-semibold">
                              {c.name
                                .split(' ')
                                .map((n) => n[0])
                                .filter(Boolean)
                                .join('')
                                .toUpperCase()
                                .slice(0, 2)}
                            </AvatarFallback>
                          </Avatar>
                          <div>
                            <p className="font-semibold">{c.name || '(no name)'}</p>
                            <p className="text-sm text-muted-foreground">{c.email}</p>
                          </div>
                        </div>
                      </TableCell>
                      <TableCell className="text-sm">{c.job_title}</TableCell>
                      <TableCell>
                        <span
                          className={cn(
                            'font-semibold tabular-nums',
                            getScoreColor(c.ai_match_score),
                          )}
                        >
                          {c.ai_match_score != null ? `${c.ai_match_score}%` : '—'}
                        </span>
                      </TableCell>
                      <TableCell>{getStatusBadge(c.status)}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">
                        {c.applied_at ? format(new Date(c.applied_at), 'MMM d, yyyy') : '—'}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>
      </div>
    </RecruiterLayout>
  );
}
