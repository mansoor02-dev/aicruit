'use client';

import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { mockJobs, mockInterviews, analyticsData } from '@/data/mockData';
import { Users, Calendar, Brain, ClipboardCheck, ArrowRight, Sparkles, TrendingUp, Filter, Download } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { format, parseISO } from 'date-fns';
import Link from 'next/link';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';

export default function Dashboard() {
  const scheduledInterviews = mockInterviews.filter(i => i.status === 'scheduled');
  const recentJobs = mockJobs.filter(j => j.status === 'Open').slice(0, 4);

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between flex-wrap gap-4">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Analytics Overview</h1>
            <p className="text-muted-foreground mt-1">Track your recruitment performance at a glance</p>
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

        {/* Stats Cards - staggered */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          {[
            { title: 'Total Applicants', value: '36K', trend: 12.12, icon: <Users className="w-5 h-5" /> },
            { title: 'Interviews Conducted', value: scheduledInterviews.length + 42, trend: 24.1, icon: <Calendar className="w-5 h-5" /> },
            { title: 'Avg AI Match Score', value: '78%', trend: -4.12, icon: <Brain className="w-5 h-5" /> },
            { title: 'Pending Reviews', value: 15, trend: 6.25, icon: <ClipboardCheck className="w-5 h-5" /> },
          ].map((s, idx) => (
            <div key={s.title} className="animate-fade-in-up" style={{ animationDelay: `${idx * 75}ms` }}>
              <StatsCard
                title={s.title}
                value={s.value}
                trend={s.trend}
                trendLabel="vs last year"
                icon={s.icon}
              />
            </div>
          ))}
        </div>

        {/* Main Chart */}
        <Card className="bg-card border-border animate-fade-in-up" style={{ animationDelay: '300ms' } as React.CSSProperties}>
          <CardHeader className="flex flex-row items-center justify-between gap-2 pb-4">
            <div className="flex items-center gap-2">
              <div className="w-9 h-9 rounded-lg bg-accent text-accent-foreground flex items-center justify-center">
                <Users className="w-4 h-4" />
              </div>
              <CardTitle className="text-base font-semibold">Total Applicants</CardTitle>
            </div>
            <Badge variant="success">
              <TrendingUp className="w-3 h-3 mr-1" /> +12.12%
            </Badge>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-3 mb-1">
              <span className="text-4xl font-extrabold tracking-tight text-foreground">36,250,224</span>
            </div>
            <p className="text-sm text-muted-foreground mb-6">Last 12 months</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={analyticsData.monthlyData}>
                  <defs>
                    <linearGradient id="applicantsFill" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.35} />
                      <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" vertical={false} />
                  <XAxis dataKey="month" stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="hsl(var(--muted-foreground))" fontSize={12} tickLine={false} axisLine={false} />
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
          {/* My Agenda */}
          <Card className="bg-card border-border animate-fade-in-up" style={{ animationDelay: '380ms' } as React.CSSProperties}>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-accent text-accent-foreground flex items-center justify-center">
                  <Calendar className="w-4 h-4" />
                </div>
                <CardTitle className="text-base font-semibold">My Agenda</CardTitle>
              </div>
              <Button variant="outline" size="sm">See Calendar</Button>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="meetings">
                <TabsList className="mb-4 bg-muted p-1">
                  <TabsTrigger value="meetings" className="data-[state=active]:bg-card data-[state=active]:shadow-sm">Meetings</TabsTrigger>
                  <TabsTrigger value="events" className="data-[state=active]:bg-card data-[state=active]:shadow-sm">Events</TabsTrigger>
                  <TabsTrigger value="holiday" className="data-[state=active]:bg-card data-[state=active]:shadow-sm">Holiday</TabsTrigger>
                </TabsList>
                <TabsContent value="meetings" className="space-y-2.5">
                  {scheduledInterviews.length === 0 && (
                    <p className="text-muted-foreground text-sm py-8 text-center">No meetings scheduled</p>
                  )}
                  {scheduledInterviews.map((interview) => (
                    <div
                      key={interview.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-muted/40 border border-border hover:bg-accent hover:border-primary/30 transition-all duration-200 ease-smooth"
                    >
                      <div className="min-w-0">
                        <p className="font-semibold text-foreground truncate">{interview.candidateName}</p>
                        <p className="text-sm text-muted-foreground truncate">{interview.jobTitle}</p>
                      </div>
                      <div className="text-right shrink-0 ml-3">
                        <p className="text-sm font-semibold text-foreground">
                          {format(parseISO(interview.scheduledAt), 'MMM d')}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {format(parseISO(interview.scheduledAt), 'h:mm a')}
                        </p>
                      </div>
                    </div>
                  ))}
                </TabsContent>
                <TabsContent value="events">
                  <p className="text-muted-foreground text-sm py-8 text-center">No upcoming events</p>
                </TabsContent>
                <TabsContent value="holiday">
                  <p className="text-muted-foreground text-sm py-8 text-center">No upcoming holidays</p>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          {/* Recently Opened Positions */}
          <Card className="bg-card border-border animate-fade-in-up" style={{ animationDelay: '460ms' } as React.CSSProperties}>
            <CardHeader className="flex flex-row items-center justify-between pb-4">
              <div className="flex items-center gap-2">
                <div className="w-9 h-9 rounded-lg bg-accent text-accent-foreground flex items-center justify-center">
                  <Sparkles className="w-4 h-4" />
                </div>
                <CardTitle className="text-base font-semibold">Recently Opened Positions</CardTitle>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href="/recruiter/job">All Positions</Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-2.5">
              {recentJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-muted/40 border border-border hover:bg-accent hover:border-primary/30 transition-all duration-200 ease-smooth"
                >
                  <div className="min-w-0">
                    <p className="font-semibold text-foreground truncate">{job.title}</p>
                    <p className="text-sm text-muted-foreground truncate">{job.location} · {job.experienceLevel}</p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <Badge variant="soft">NEW</Badge>
                    <Badge variant="success">Active</Badge>
                    <Button variant="ghost" size="sm" asChild>
                      <Link href={`/recruiter/job/${job.id}`}>
                        Details <ArrowRight className="w-3 h-3 ml-1" />
                      </Link>
                    </Button>
                  </div>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
      </div>
    </RecruiterLayout>
  );
}