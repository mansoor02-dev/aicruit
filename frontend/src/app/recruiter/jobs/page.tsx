'use client';

import { useState, useEffect } from 'react';
import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { mockJobs, Job } from '@/data/mockData';
import { Plus, Search, Eye, Edit, X, Loader2 } from 'lucide-react';
import Link from 'next/link';
import { format, parseISO } from 'date-fns';
import { useToast } from '@/hooks/use-toast';
import { api } from '@/lib/api';

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
}

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newJob, setNewJob] = useState({
    title: '',
    description: '',
    type: 'Remote' as Job['type'],
    location: '',
    experienceLevel: 'Mid-level' as Job['experienceLevel'],
    salaryMin: '',
    salaryMax: '',
    requiredSkills: [] as string[],
    status: 'Draft' as Job['status'],
  });
  const [skillInput, setSkillInput] = useState('');
  const { toast } = useToast();

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const response: JobApiResponse[] = await api.get('/jobs');
      const mappedJobs: Job[] = response.map(job => ({
        id: job.id,
        title: job.title,
        company: job.company_name || 'Your Company',
        location: job.location,
        type: job.type as Job['type'],
        experienceLevel: job.experience_level as Job['experienceLevel'],
        salaryMin: job.salary_min || 0,
        salaryMax: job.salary_max || 0,
        requiredSkills: job.required_skills,
        description: job.description,
        status: (job.status === 'OPEN' ? 'Open' : job.status === 'CLOSED' ? 'Closed' : 'Draft') as Job['status'],
        applicants: 0, // This would need a separate API call or be included in response
        createdAt: new Date(job.created_at).toISOString().split('T')[0],
      }));
      setJobs(mappedJobs);
    } catch (error) {
      console.error('Failed to fetch jobs:', error);
      toast({
        title: 'Error',
        description: 'Failed to load jobs. Please try again.',
        variant: 'destructive',
      });
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

  const filteredJobs = jobs.filter(job => 
    job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.location.toLowerCase().includes(searchTerm.toLowerCase())
  );

  const handleAddSkill = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && skillInput.trim()) {
      e.preventDefault();
      if (!newJob.requiredSkills.includes(skillInput.trim())) {
        setNewJob(prev => ({
          ...prev,
          requiredSkills: [...prev.requiredSkills, skillInput.trim()]
        }));
      }
      setSkillInput('');
    }
  };

  const handleRemoveSkill = (skill: string) => {
    setNewJob(prev => ({
      ...prev,
      requiredSkills: prev.requiredSkills.filter(s => s !== skill)
    }));
  };

  const handleCreateJob = async () => {
    if (!newJob.title || !newJob.description || !newJob.location) {
      toast({
        title: 'Error',
        description: 'Please fill in all required fields',
        variant: 'destructive',
      });
      return;
    }

    const salaryMin = parseInt(newJob.salaryMin);
    const salaryMax = parseInt(newJob.salaryMax);
    
    if (salaryMax <= salaryMin) {
      toast({
        title: 'Error',
        description: 'Maximum salary must be greater than minimum salary',
        variant: 'destructive',
      });
      return;
    }

    try {
      setCreating(true);
      const jobData = {
        title: newJob.title,
        description: newJob.description,
        location: newJob.location,
        type: newJob.type,
        salary_min: salaryMin || null,
        salary_max: salaryMax || null,
        required_skills: newJob.requiredSkills,
        experience_level: newJob.experienceLevel,
      };

      await api.post('/jobs', jobData);

      // Reset form
      setNewJob({
        title: '',
        description: '',
        type: 'Remote',
        location: '',
        experienceLevel: 'Mid-level',
        salaryMin: '',
        salaryMax: '',
        requiredSkills: [],
        status: 'Draft',
      });
      setIsDialogOpen(false);

      toast({
        title: 'Success',
        description: 'Job created successfully',
      });

      // Refresh jobs list
      await fetchJobs();
    } catch (error) {
      console.error('Failed to create job:', error);
      toast({
        title: 'Error',
        description: 'Failed to create job. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setCreating(false);
    }
  };

  const getStatusBadge = (status: Job['status']) => {
    switch (status) {
      case 'Open':
        return <Badge className="bg-green-500/20 text-green-500 border-green-500/30">Open</Badge>;
      case 'Closed':
        return <Badge variant="secondary">Closed</Badge>;
      case 'Draft':
        return <Badge variant="outline">Draft</Badge>;
    }
  };

  if (!mounted) {
    return (
      <RecruiterLayout>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-foreground">Jobs Management</h1>
              <p className="text-muted-foreground">Create and manage your job postings</p>
            </div>
          </div>
          <div className="flex items-center justify-center py-8">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        </div>
      </RecruiterLayout>
    );
  }

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-foreground">Jobs Management</h1>
            <p className="text-muted-foreground">Create and manage your job postings</p>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="w-4 h-4 mr-2" />
                Create New Job
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl bg-card max-h-[90vh] overflow-y-auto">
              <DialogHeader>
                <DialogTitle>Create New Job</DialogTitle>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label htmlFor="title">Job Title *</Label>
                  <Input
                    id="title"
                    placeholder="e.g., Senior Frontend Developer"
                    value={newJob.title}
                    onChange={(e) => setNewJob(prev => ({ ...prev, title: e.target.value }))}
                    className="bg-background"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="description">Description *</Label>
                  <Textarea
                    id="description"
                    placeholder="Describe the role and responsibilities..."
                    value={newJob.description}
                    onChange={(e) => setNewJob(prev => ({ ...prev, description: e.target.value }))}
                    rows={4}
                    className="bg-background"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="type">Job Type</Label>
                    <Select 
                      value={newJob.type} 
                      onValueChange={(v) => setNewJob(prev => ({ ...prev, type: v as Job['type'] }))}
                    >
                      <SelectTrigger className="bg-background">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-popover">
                        <SelectItem value="Remote">Remote</SelectItem>
                        <SelectItem value="Onsite">Onsite</SelectItem>
                        <SelectItem value="Hybrid">Hybrid</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="location">Location *</Label>
                    <Input
                      id="location"
                      placeholder="e.g., San Francisco, CA"
                      value={newJob.location}
                      onChange={(e) => setNewJob(prev => ({ ...prev, location: e.target.value }))}
                      className="bg-background"
                    />
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="experience">Experience Level</Label>
                    <Select 
                      value={newJob.experienceLevel} 
                      onValueChange={(v) => setNewJob(prev => ({ ...prev, experienceLevel: v as Job['experienceLevel'] }))}
                    >
                      <SelectTrigger className="bg-background">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-popover">
                        <SelectItem value="Junior">Junior</SelectItem>
                        <SelectItem value="Mid-level">Mid-level</SelectItem>
                        <SelectItem value="Senior">Senior</SelectItem>
                        <SelectItem value="Lead">Lead</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="status">Status</Label>
                    <Select 
                      value={newJob.status} 
                      onValueChange={(v) => setNewJob(prev => ({ ...prev, status: v as Job['status'] }))}
                    >
                      <SelectTrigger className="bg-background">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent className="bg-popover">
                        <SelectItem value="Draft">Draft</SelectItem>
                        <SelectItem value="Open">Open</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="salaryMin">Min Salary ($)</Label>
                    <Input
                      id="salaryMin"
                      type="number"
                      placeholder="e.g., 80000"
                      value={newJob.salaryMin}
                      onChange={(e) => setNewJob(prev => ({ ...prev, salaryMin: e.target.value }))}
                      className="bg-background"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="salaryMax">Max Salary ($)</Label>
                    <Input
                      id="salaryMax"
                      type="number"
                      placeholder="e.g., 120000"
                      value={newJob.salaryMax}
                      onChange={(e) => setNewJob(prev => ({ ...prev, salaryMax: e.target.value }))}
                      className="bg-background"
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <Label htmlFor="skills">Required Skills</Label>
                  <Input
                    id="skills"
                    placeholder="Type a skill and press Enter"
                    value={skillInput}
                    onChange={(e) => setSkillInput(e.target.value)}
                    onKeyDown={handleAddSkill}
                    className="bg-background"
                  />
                  {newJob.requiredSkills.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {newJob.requiredSkills.map((skill) => (
                        <Badge key={skill} variant="secondary" className="gap-1">
                          {skill}
                          <button onClick={() => handleRemoveSkill(skill)}>
                            <X className="w-3 h-3" />
                          </button>
                        </Badge>
                      ))}
                    </div>
                  )}
                </div>

                <div className="flex justify-end gap-3 pt-4">
                  <Button variant="outline" onClick={() => setIsDialogOpen(false)}>
                    Cancel
                  </Button>
                  <Button onClick={handleCreateJob} disabled={creating}>
                    {creating ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Creating...
                      </>
                    ) : (
                      'Create Job'
                    )}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search jobs..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="pl-10 bg-card"
          />
        </div>

        {/* Jobs Table */}
        <Card className="bg-card border-border">
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Job Title</TableHead>
                  <TableHead>Date Posted</TableHead>
                  <TableHead>Applicants</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {loading ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8">
                      <div className="flex items-center justify-center gap-2">
                        <Loader2 className="w-4 h-4 animate-spin" />
                        Loading jobs...
                      </div>
                    </TableCell>
                  </TableRow>
                ) : filteredJobs.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                      No jobs found. Create your first job posting.
                    </TableCell>
                  </TableRow>
                ) : (
                  filteredJobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell>
                        <div>
                          <p className="font-medium">{job.title}</p>
                          <p className="text-sm text-muted-foreground">{job.location} · {job.type}</p>
                        </div>
                      </TableCell>
                      <TableCell>{format(parseISO(job.createdAt), 'MMM d, yyyy')}</TableCell>
                      <TableCell>{job.applicants}</TableCell>
                      <TableCell>{getStatusBadge(job.status)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="icon" asChild>
                            <Link href={`/recruiter/jobs/${job.id}`}>
                              <Eye className="w-4 h-4" />
                            </Link>
                          </Button>
                          <Button variant="ghost" size="icon">
                            <Edit className="w-4 h-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </div>
    </RecruiterLayout>
  );
}

