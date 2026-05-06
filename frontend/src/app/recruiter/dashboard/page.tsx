'use client';

import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  Users,
  Calendar,
  Brain,
  ClipboardCheck,
  ArrowRight,
  Sparkles,
  TrendingUp,
  Filter,
  Download,
  Briefcase,
} from 'lucide-react';
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useQuery } from '@tanstack/react-query';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { api } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';

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

function getStatusBadge(status: string) {
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
}

function relativeTime(iso: string): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diffMs = Date.now() - then;
  const sec = Math.max(0, Math.floor(diffMs / 1000));
  if (sec < 60) return `${sec}s ago`;
  const min = Math.floor(sec / 60);
  if (min < 60) return `${min}m ago`;
  const hr = Math.floor(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.floor(hr / 24);
  if (day < 30) return `${day}d ago`;
  const mo = Math.floor(day / 30);
  if (mo < 12) return `${mo}mo ago`;
  return `${Math.floor(mo / 12)}y ago`;
}

// Small, realistic mock chart data (weekly applicants)
const weeklyApplicants = [
  { label: 'Mon', applicants: 1 },
  { label: 'Tue', applicants: 3 },
  { label: 'Wed', applicants: 2 },
  { label: 'Thu', applicants: 4 },
  { label: 'Fri', applicants: 2 },
  { label: 'Sat', applicants: 5 },
  { label: 'Sun', applicants: 3 },
];

// Small, realistic mock funnel
const funnel = [
  { label: 'Applied', value: 12 },
  { label: 'Screened', value: 7 },
  { label: 'Interviewed', value: 5 },
  { label: 'Offered', value: 2 },
  { label: 'Hired', value: 1 },
];

export default function Dashboard() {
  const router = useRouter();
  const { user } = useAuth();

  const { data, isLoading, isError } = useQuery({
    queryKey: ['recruiter-dashboard-applications'],
    queryFn: () => api.get<AllCandidateRow[]>('/job/candidates/all'),
  });

  const applications = data ?? [];
  const recent = [...applications]
    .sort((a, b) => new Date(b.applied_at).getTime() - new Date(a.applied_at).getTime())
    .slice(0, 6);

  // Real number we can compute cheaply; everything else stays mock and small.
  const realApplicantCount = applications.length;

  const kpis = [
    { title: 'Total Jobs Posted', value: 4, trend: 0, icon: <Briefcase className="w-5 h-5" /> },
    { title: 'Active Jobs', value: 3, trend: 0, icon: <Sparkles className="w-5 h-5" /> },
    {
      title: 'Total Applicants',
      value: realApplicantCount > 0 ? realApplicantCount : 12,
      trend: 8.3,
      icon: <Users className="w-5 h-5" />,
    },
    { title: 'Interviews Scheduled', value: 5, trend: 12.5, icon: <Calendar className="w-5 h-5" /> },
  ];

  const secondaryKpis = [
    { title: 'Interviews Completed', value: 2 },
    { title: 'Offers Extended', value: 1 },
    { title: 'Hires This Month', value: 1 },
    { title: 'Avg Time to Hire', value: '8 days' },
    { title: 'Avg AI Match Score', value: '72%' },
    { title: 'Acceptance Rate', value: '80%' },
  ];

  const displayName = user?.name || user?.email?.split('@')[0] || 'there';
  const roleLabel = user?.role ? user.role.charAt(0) + user.role.slice(1).toLowerCase() : 'Recruiter';

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div className="flex items-center gap-3">
            <Avatar className="ring-2 ring-primary/15 h-12 w-12">
              <AvatarFallback className="bg-accent text-accent-foreground font-semibold">
                {(user?.name || user?.email || 'R')
                  .split(' ')
                  .map((n) => n[0])
                  .filter(Boolean)
                  .join('')
                  .toUpperCase()
                  .slice(0, 2)}
              </AvatarFallback>
            </Avatar>
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-foreground">
                Welcome back, {displayName}
              </h1>
              <p className="text-muted-foreground mt-1 text-sm">
                {roleLabel}
                {user?.email ? ` · ${user.email}` : ''}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline">
              <Filter className="w-4 h-4" /> Filter
            </Button>
            <Button>
              <Download className="w-4 h-4" /> Export
            </Button>
          </div>
        </div>

        {/* KPI Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {kpis.map((s, idx) => (
            <div key={s.title} className="animate-fade-in-up" style={{ animationDelay: `${idx * 75}ms` }}>
              <StatsCard
                title={s.title}
                value={s.value}
                trend={s.trend}
                trendLabel="vs last month"
                icon={s.icon}
              />
            </div>
          ))}
        </div>

        {/* Secondary KPIs */}
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {secondaryKpis.map((m) => (
            <Card key={m.title} className="bg-card border-border">
              <CardContent className="p-4">
                <p className="text-xs text-muted-foreground">{m.title}</p>
                <p className="text-xl font-bold tracking-tight text-foreground mt-1">{m.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>

        {/* Chart */}
        <Card className="bg-card border-border animate-fade-in-up" style={{ animationDelay: '300ms' } as React.CSSProperties}>
          <CardHeader className="flex flex-row items-center justify-between gap-2 pb-4">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-lg bg-accent text-accent-foreground flex items-center justify-center">
                <Users className="w-4 h-4" />
              </div>
              <CardTitle className="text-base font-semibold">Applicants This Week</CardTitle>
            </div>
            <Badge variant="success">
              <TrendingUp className="w-3 h-3 mr-1" /> +3 vs last week
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-3 mb-1">
              <span className="text-4xl font-extrabold tracking-tight text-foreground">20</span>
              <span className="text-sm text-muted-foreground">applicants</span>
            </div>
            <p className="text-sm text-muted-foreground mb-6">Last 7 days</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={weeklyApplicants}>
                  <defs>
                    <linearGradient id="applicantsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="label" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--popover))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '12px',
                      color: 'hsl(var(--popover-foreground))',
                      boxShadow: 'var(--shadow-md)',
                    }}
                  />
                  <Area
                    type="monotone"
                    dataKey="applicants"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2.5}
                    fill="url(#applicantsFill)"
                    activeDot={{ r: 6, fill: 'hsl(var(--primary))', strokeWidth: 2, stroke: 'hsl(var(--card))' }}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Bottom Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Recent Applications (REAL) */}
          <Card className="bg-card border-border animate-fade-in-up" style={{ animationDelay: '380ms' } as React.CSSProperties}>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-accent text-accent-foreground flex items-center justify-center">
                  <Users className="w-4 h-4" />
                </div>
                <CardTitle className="text-base font-semibold">Recent Applications</CardTitle>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href="/recruiter/candidates">View All</Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {isLoading ? (
                <>
                  {Array.from({ length: 4 }).map((_, i) => (
                    <Skeleton key={i} className="h-14 w-full rounded-lg" />
                  ))}
                </>
              ) : isError || recent.length === 0 ? (
                <div className="py-10 text-center">
                  <ClipboardCheck className="w-8 h-8 text-muted-foreground mx-auto mb-2 opacity-60" />
                  <p className="text-sm text-muted-foreground">
                    No applications yet — share your job link to start collecting candidates.
                  </p>
                </div>
              ) : (
                recent.map((row) => (
                  <button
                    key={row.application_id}
                    onClick={() => router.push(`/recruiter/job/${row.job_id}/candidate/${row.application_id}`)}
                    className="w-full flex items-center justify-between p-3 rounded-lg bg-muted/40 border border-border hover:bg-accent hover:border-primary/30 transition-all duration-200 ease-smooth text-left"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <Avatar className="ring-2 ring-primary/15 h-9 w-9 shrink-0">
                        <AvatarFallback className="bg-accent text-accent-foreground font-semibold text-xs">
                          {(row.name || row.email || '?')
                            .split(' ')
                            .map((n) => n[0])
                            .filter(Boolean)
                            .join('')
                            .toUpperCase()
                            .slice(0, 2)}
                        </AvatarFallback>
                      </Avatar>
                      <div className="min-w-0">
                        <p className="font-semibold text-foreground truncate">{row.name || '(no name)'}</p>
                        <p className="text-sm text-muted-foreground truncate">{row.job_title}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 shrink-0 ml-3">
                      {getStatusBadge(row.status)}
                      <span className="text-xs text-muted-foreground tabular-nums w-14 text-right">
                        {relativeTime(row.applied_at)}
                      </span>
                      <ArrowRight className="w-3.5 h-3.5 text-muted-foreground" />
                    </div>
                  </button>
                ))
              )}
            </CardContent>
          </Card>

          {/* Pipeline Funnel (mock) */}
          <Card className="bg-card border-border animate-fade-in-up" style={{ animationDelay: '460ms' } as React.CSSProperties}>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-accent text-accent-foreground flex items-center justify-center">
                  <Brain className="w-4 h-4" />
                </div>
                <CardTitle className="text-base font-semibold">Pipeline Conversion</CardTitle>
              </div>
              <Tabs defaultValue="all">
                <TabsList className="bg-muted p-1">
                  <TabsTrigger value="all" className="data-[state=active]:bg-card data-[state=active]:shadow-sm text-xs">All Jobs</TabsTrigger>
                  <TabsTrigger value="month" className="data-[state=active]:bg-card data-[state=active]:shadow-sm text-xs">This Month</TabsTrigger>
                </TabsList>
              </Tabs>
            </CardHeader>
            <CardContent className="space-y-3">
              {funnel.map((step) => {
                const max = funnel[0].value;
                const pct = Math.max(8, Math.round((step.value / max) * 100));
                return (
                  <div key={step.label}>
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm font-medium text-foreground">{step.label}</span>
                      <span className="text-sm font-semibold tabular-nums text-foreground">{step.value}</span>
                    </div>
                    <div className="h-2 rounded-full bg-muted overflow-hidden">
                      <div
                        className="h-full bg-primary rounded-full transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                  </div>
                );
              })}
            </CardContent>
          </Card>
        </div>
      </div>
    </RecruiterLayout>
  );
}
