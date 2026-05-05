'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { CandidateLayout } from '@/components/layout/CandidateLayout';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Job } from '@/data/mockData';
import {
  MapPin,
  Briefcase,
  DollarSign,
  Search,
  Filter,
  Building2,
  Loader2
} from 'lucide-react';
import { api } from '@/lib/api';

type ApplicationQuestionType = "text" | "textarea" | "number" | "date" | "select" | "yes_no" | "email" | "url";

interface ApplicationQuestion {
  id: string;
  label: string;
  help_text?: string;
  type: ApplicationQuestionType;
  required: boolean;
  min_length?: number | null;
  max_length?: number | null;
  min_value?: number | null;
  max_value?: number | null;
  options?: string[];
}

interface JobApiResponse {
  id: string;
  title: string;
  description: string;
  location: string;
  type: string;
  salary_min: number | null;
  salary_max: number | null;
  required_skills: string[];
  experience_level: string;
  company_id: string;
  recruiter_id: string;
  status: string;
  created_at: string;
  company_name?: string;
  application_questions?: ApplicationQuestion[];
}

export default function CandidateJobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('all');
  const [experienceFilter, setExperienceFilter] = useState('all');

  const fetchJobs = async () => {
    try {
      console.log('Fetching jobs...');
      setLoading(true);
      const response: JobApiResponse[] = await api.get('/job');
      console.log('Jobs response:', response);
      const mappedJobs: Job[] = response
        .filter(job => job.status === 'OPEN') // Only show open jobs for candidates
        .map(job => ({
          id: job.id,
          title: job.title,
          company: job.company_name || 'Company',
          location: job.location,
          type: job.type as Job['type'],
          experienceLevel: job.experience_level as Job['experienceLevel'],
          salaryMin: job.salary_min || 0,
          salaryMax: job.salary_max || 0,
          requiredSkills: job.required_skills,
          description: job.description,
          status: 'Open' as Job['status'],
          applicants: 0, // This would need a separate API call
          createdAt: new Date(job.created_at).toISOString().split('T')[0],
        }));
      console.log('Mapped jobs:', mappedJobs);
      setJobs(mappedJobs);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      // Don't show toast for now, just log
      // toast({
      //   title: 'Error',
      //   description: 'Failed to load jobs. Please try again.',
      //   variant: 'destructive',
      // });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchJobs();
  }, []);

  useEffect(() => {
    setMounted(true);
  }, []);

  const openJobs = jobs.filter(j => j.status === 'Open');

  const filteredJobs = openJobs.filter(job => {
    const matchesSearch = job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
      job.requiredSkills.some(s => s.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesLocation = locationFilter === 'all' || job.type === locationFilter;
    const matchesExperience = experienceFilter === 'all' || job.experienceLevel === experienceFilter;
    return matchesSearch && matchesLocation && matchesExperience;
  });

  if (!mounted) {
    return (
      <div className="min-h-screen bg-background p-4">
        <div className="space-y-6">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Browse Jobs</h1>
            <p className="text-muted-foreground mt-1">Find your next opportunity</p>
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
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Browse Jobs</h1>
          <p className="text-muted-foreground mt-1">Find your next opportunity</p>
        </div>

        {/* Filters */}
        <div className="flex flex-col md:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search by title or skill..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-10 bg-card"
            />
          </div>
          <Select value={locationFilter} onValueChange={setLocationFilter}>
            <SelectTrigger className="w-full md:w-48 bg-card">
              <Filter className="w-4 h-4 mr-2" />
              <SelectValue placeholder="Location" />
            </SelectTrigger>
            <SelectContent className="bg-popover">
              <SelectItem value="all">All Locations</SelectItem>
              <SelectItem value="Remote">Remote</SelectItem>
              <SelectItem value="Onsite">Onsite</SelectItem>
              <SelectItem value="Hybrid">Hybrid</SelectItem>
            </SelectContent>
          </Select>
          <Select value={experienceFilter} onValueChange={setExperienceFilter}>
            <SelectTrigger className="w-full md:w-48 bg-card">
              <SelectValue placeholder="Experience" />
            </SelectTrigger>
            <SelectContent className="bg-popover">
              <SelectItem value="all">All Levels</SelectItem>
              <SelectItem value="Junior">Junior</SelectItem>
              <SelectItem value="Mid-level">Mid-level</SelectItem>
              <SelectItem value="Senior">Senior</SelectItem>
              <SelectItem value="Lead">Lead</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Jobs Grid */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-6">
          {loading ? (
            // Loading skeleton
            Array.from({ length: 6 }).map((_, i) => {
              return (
                <Card key={i} className="bg-card border-border">
                  <CardHeader className="pb-3">
                    <div className="flex items-start justify-between">
                      <div className="p-2 bg-primary/10 rounded-lg">
                        <Building2 className="w-6 h-6 text-primary" />
                      </div>
                      <div className="h-6 w-16 bg-muted rounded animate-pulse" />
                    </div>
                    <div className="pt-3 space-y-2">
                      <div className="h-5 bg-muted rounded animate-pulse" />
                      <div className="h-4 w-3/4 bg-muted rounded animate-pulse" />
                    </div>
                  </CardHeader>
                  <CardContent className="space-y-3">
                    <div className="h-4 bg-muted rounded animate-pulse" />
                    <div className="h-4 bg-muted rounded animate-pulse" />
                    <div className="h-4 bg-muted rounded animate-pulse" />
                    <div className="flex gap-2">
                      <div className="h-6 w-16 bg-muted rounded animate-pulse" />
                      <div className="h-6 w-20 bg-muted rounded animate-pulse" />
                    </div>
                  </CardContent>
                </Card>
              );
            })
          ) : filteredJobs.length === 0 ? (
            <div className="col-span-full text-center py-12">
              <p className="text-muted-foreground mt-1">No jobs found matching your criteria</p>
            </div>
          ) : (
            filteredJobs.map((job) => {
              return (
                <Link
                  key={job.id}
                  href={`/candidate/job/${job.id}`}
                  className="block focus:outline-none focus-visible:ring-2 focus-visible:ring-primary rounded-lg"
                >
                  <Card className="bg-card border-border hover:shadow-lg hover:border-primary/30 transition-all cursor-pointer h-full">
                    <CardHeader className="pb-3">
                      <div className="flex items-start justify-between">
                        <div className="p-2 bg-primary/10 rounded-lg">
                          <Building2 className="w-6 h-6 text-primary" />
                        </div>
                        <Badge variant="secondary">{job.type}</Badge>
                      </div>
                      <div className="pt-3">
                        <h3 className="text-lg font-semibold text-foreground">{job.title}</h3>
                        <p className="text-muted-foreground mt-1">{job.company}</p>
                      </div>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <MapPin className="w-4 h-4" />
                        {job.location}
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Briefcase className="w-4 h-4" />
                        {job.experienceLevel}
                      </div>
                      <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <DollarSign className="w-4 h-4" />
                        ${job.salaryMin.toLocaleString()} - ${job.salaryMax.toLocaleString()}
                      </div>
                      <div className="flex flex-wrap gap-2 pt-2">
                        {job.requiredSkills.slice(0, 3).map((skill) => {
                          return (
                            <Badge key={skill} variant="outline" className="text-xs">
                              {skill}
                            </Badge>
                          );
                        })}
                        {job.requiredSkills.length > 3 && (
                          <Badge variant="outline" className="text-xs">
                            +{job.requiredSkills.length - 3}
                          </Badge>
                        )}
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })
          )}
        </div>
      </div>
    </CandidateLayout>
  );
}

