'use client';

import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { StatsCard } from '@/components/dashboard/StatsCard';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { mockJobs, mockInterviews, analyticsData } from '@/data/mockData';
import { Users, Calendar, Brain, ClipboardCheck, ArrowRight, Sparkles } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
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
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Analytics Overview</h1>
            <p className="text-muted-foreground">Learn and discover about your recruitment performance</p>
          </div>
          <div className="flex items-center gap-3">
            <Button variant="outline">
              Filter
            </Button>
            <Button>
              Export
            </Button>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatsCard
            title="Total Applicants"
            value="36K"
            trend={12.12}
            trendLabel="Better than last year"
            icon={<Users className="w-5 h-5 text-accent-foreground" />}
          />
          <StatsCard
            title="Interviews Conducted"
            value={scheduledInterviews.length + 42}
            trend={24.1}
            trendLabel="Better than last year"
            icon={<Calendar className="w-5 h-5 text-accent-foreground" />}
          />
          <StatsCard
            title="Avg AI Match Score"
            value="78%"
            trend={-4.12}
            trendLabel="Better than last year"
            icon={<Brain className="w-5 h-5 text-accent-foreground" />}
          />
          <StatsCard
            title="Pending Reviews"
            value={15}
            trend={6.25}
            trendLabel="Worst than last year"
            icon={<ClipboardCheck className="w-5 h-5 text-accent-foreground" />}
          />
        </div>

        {/* Main Chart */}
        <Card className="bg-card border-border">
          <CardHeader className="flex flex-row items-center gap-2">
            <Users className="w-5 h-5 text-muted-foreground" />
            <CardTitle className="text-base font-semibold">Total Applicants</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-baseline gap-3 mb-2">
              <span className="text-4xl font-bold text-foreground">36,250,224</span>
              <span className="text-sm text-green-500 font-medium flex items-center gap-1">
                ↗ 12.12%
              </span>
            </div>
            <p className="text-sm text-muted-foreground mb-6">Last 1 year's data</p>
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <LineChart data={analyticsData.monthlyData}>
                  <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                  <XAxis
                    dataKey="month"
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                  />
                  <YAxis
                    stroke="hsl(var(--muted-foreground))"
                    fontSize={12}
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'hsl(var(--popover))',
                      border: '1px solid hsl(var(--border))',
                      borderRadius: '8px',
                      color: 'hsl(var(--popover-foreground))'
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="applicants"
                    stroke="hsl(var(--primary))"
                    strokeWidth={2}
                    dot={{ fill: 'hsl(var(--primary))', strokeWidth: 2 }}
                    activeDot={{ r: 6, fill: 'hsl(var(--primary))' }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </CardContent>
        </Card>

        {/* Bottom Section */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* My Agenda */}
          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <Calendar className="w-5 h-5 text-muted-foreground" />
                <CardTitle className="text-base font-semibold">My Agenda</CardTitle>
              </div>
              <Button variant="outline" size="sm">See Calendar</Button>
            </CardHeader>
            <CardContent>
              <Tabs defaultValue="meetings">
                <TabsList className="mb-4 bg-muted">
                  <TabsTrigger value="meetings">Meetings</TabsTrigger>
                  <TabsTrigger value="events">Events</TabsTrigger>
                  <TabsTrigger value="holiday">Holiday</TabsTrigger>
                </TabsList>
                <TabsContent value="meetings" className="space-y-3">
                  {scheduledInterviews.map((interview) => (
                    <div
                      key={interview.id}
                      className="flex items-center justify-between p-3 rounded-lg bg-background border border-border"
                    >
                      <div>
                        <p className="font-medium text-foreground">{interview.candidateName}</p>
                        <p className="text-sm text-muted-foreground">{interview.jobTitle}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm font-medium text-foreground">
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
                  <p className="text-muted-foreground text-sm">No upcoming events</p>
                </TabsContent>
                <TabsContent value="holiday">
                  <p className="text-muted-foreground text-sm">No upcoming holidays</p>
                </TabsContent>
              </Tabs>
            </CardContent>
          </Card>

          {/* Recently Opened Positions */}
          <Card className="bg-card border-border">
            <CardHeader className="flex flex-row items-center justify-between">
              <div className="flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-muted-foreground" />
                <CardTitle className="text-base font-semibold">Recently Opened Positions</CardTitle>
              </div>
              <Button variant="outline" size="sm" asChild>
                <Link href="/recruiter/job">All Positions</Link>
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              {recentJobs.map((job) => (
                <div
                  key={job.id}
                  className="flex items-center justify-between p-3 rounded-lg bg-background border border-border"
                >
                  <div>
                    <p className="font-medium text-foreground">{job.title}</p>
                    <p className="text-sm text-muted-foreground">{job.location} · {job.experienceLevel}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="bg-primary/10 text-primary border-primary/20">
                      NEW
                    </Badge>
                    <Badge variant="secondary">Active</Badge>
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

