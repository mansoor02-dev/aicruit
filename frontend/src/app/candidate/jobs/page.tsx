'use client';

import { useState } from 'react';
import { CandidateLayout } from '@/components/layout/CandidateLayout';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { mockJobs, Job } from '@/data/mockData';
import { 
  MapPin, 
  Briefcase, 
  DollarSign, 
  Search,
  Filter,
  Building2
} from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

export default function CandidateJobs() {
  const [searchTerm, setSearchTerm] = useState('');
  const [locationFilter, setLocationFilter] = useState('all');
  const [experienceFilter, setExperienceFilter] = useState('all');
  const [appliedJobs, setAppliedJobs] = useState<string[]>([]);
  const { toast } = useToast();

  const openJobs = mockJobs.filter(j => j.status === 'Open');

  const filteredJobs = openJobs.filter(job => {
    const matchesSearch = job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         job.requiredSkills.some(s => s.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesLocation = locationFilter === 'all' || job.type === locationFilter;
    const matchesExperience = experienceFilter === 'all' || job.experienceLevel === experienceFilter;
    return matchesSearch && matchesLocation && matchesExperience;
  });

  const handleApply = (jobId: string) => {
    setAppliedJobs(prev => [...prev, jobId]);
    toast({
      title: 'Application submitted',
      description: 'Your application has been sent successfully!',
    });
  };

  return (
    <CandidateLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Browse Jobs</h1>
          <p className="text-muted-foreground">Find your next opportunity</p>
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
          {filteredJobs.map((job) => (
            <Card key={job.id} className="bg-card border-border hover:shadow-lg transition-all">
              <CardHeader className="pb-3">
                <div className="flex items-start justify-between">
                  <div className="p-2 bg-primary/10 rounded-lg">
                    <Building2 className="w-6 h-6 text-primary" />
                  </div>
                  <Badge variant="secondary">{job.type}</Badge>
                </div>
                <div className="pt-3">
                  <h3 className="text-lg font-semibold text-foreground">{job.title}</h3>
                  <p className="text-muted-foreground">{job.company}</p>
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
                  {job.requiredSkills.slice(0, 3).map((skill) => (
                    <Badge key={skill} variant="outline" className="text-xs">
                      {skill}
                    </Badge>
                  ))}
                  {job.requiredSkills.length > 3 && (
                    <Badge variant="outline" className="text-xs">
                      +{job.requiredSkills.length - 3}
                    </Badge>
                  )}
                </div>
              </CardContent>
              <CardFooter>
                {appliedJobs.includes(job.id) ? (
                  <Button disabled className="w-full" variant="secondary">
                    Applied
                  </Button>
                ) : (
                  <Button className="w-full" onClick={() => handleApply(job.id)}>
                    Quick Apply
                  </Button>
                )}
              </CardFooter>
            </Card>
          ))}
        </div>

        {filteredJobs.length === 0 && (
          <div className="text-center py-12">
            <p className="text-muted-foreground">No jobs found matching your criteria</p>
          </div>
        )}
      </div>
    </CandidateLayout>
  );
}

