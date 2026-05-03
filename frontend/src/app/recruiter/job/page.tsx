"use client";

import { useState, useEffect } from "react";
import { RecruiterLayout } from "@/components/layout/RecruiterLayout";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Job } from "@/data/mockData";
import { Plus, Search, Eye, Edit, X, Loader2, FileText, Briefcase, DollarSign, Sparkles, HelpCircle, Trash2, GripVertical } from "lucide-react";
import Link from "next/link";
import { format, parseISO } from "date-fns";
import { useToast } from "@/hooks/use-toast";
import { api } from "@/lib/api";

type QuestionType = "text" | "textarea" | "number" | "date" | "select" | "yes_no" | "email" | "url";

export interface ApplicationQuestion {
  id: string;
  label: string;
  help_text?: string;
  type: QuestionType;
  required: boolean;
  min_length?: number | null;
  max_length?: number | null;
  min_value?: number | null;
  max_value?: number | null;
  options?: string[];
}

const QUESTION_TYPE_LABELS: Record<QuestionType, string> = {
  text: "Short text",
  textarea: "Long text (paragraph)",
  number: "Number",
  date: "Date",
  select: "Multiple choice",
  yes_no: "Yes / No",
  email: "Email",
  url: "URL",
};

const newQuestion = (): ApplicationQuestion => ({
  id: "q_" + Date.now() + "_" + Math.random().toString(36).slice(2, 7),
  label: "",
  type: "text",
  required: false,
  min_length: null,
  max_length: null,
  options: [],
});

interface ApplicantInfo {
  application_id: string;
  application_status: string;
  ai_match_score: number;
  applied_at: string;
  candidate_id: string;
  candidate_name: string;
  candidate_email: string;
  candidate_phone: string;
  candidate_linkedin: string | null;
  resume_id: string;
  resume_url: string;
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
  last_date_to_apply?: string | null;
  application_questions?: ApplicationQuestion[];
  applicants?: ApplicantInfo[];
  company_name?: string;
}

type NewJobState = {
  title: string;
  description: string;
  type: Job["type"];
  location: string;
  experienceLevel: Job["experienceLevel"];
  salaryMin: string;
  salaryMax: string;
  requiredSkills: string[];
  status: Job["status"];
  last_date_to_apply: string;
};

export default function Jobs() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [isDialogOpen, setIsDialogOpen] = useState(false);
  const [creating, setCreating] = useState(false);

  const [newJob, setNewJob] = useState<NewJobState>({
    title: "",
    description: "",
    type: "Remote",
    location: "",
    experienceLevel: "Mid-level",
    salaryMin: "",
    salaryMax: "",
    requiredSkills: [],
    status: "Draft",
    last_date_to_apply: "",
  });
  const [skillInput, setSkillInput] = useState("");
  const [questions, setQuestions] = useState<ApplicationQuestion[]>([]);
  const { toast } = useToast();

  const fetchJobs = async () => {
    try {
      setLoading(true);
      const response: JobApiResponse[] = await api.get("/job");
      const mappedJobs: Job[] = response.map((job) => ({
        id: job.id,
        title: job.title,
        company: job.company_name || "Your Company",
        location: job.location,
        type: job.type as Job["type"],
        experienceLevel: job.experience_level as Job["experienceLevel"],
        salaryMin: job.salary_min || 0,
        salaryMax: job.salary_max || 0,
        requiredSkills: job.required_skills,
        description: job.description,
        status: (job.status === "OPEN" ? "Open" : job.status === "CLOSED" ? "Closed" : "Draft") as Job["status"],
        applicants: job.applicants?.length || 0,
        createdAt: new Date(job.created_at).toISOString().split("T")[0],
      }));
      setJobs(mappedJobs);
    } catch (error) {
      console.error("Failed to fetch jobs:", error);
      toast({ title: "Error", description: "Failed to load jobs. Please try again.", variant: "destructive" });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchJobs(); }, []);
  useEffect(() => { setMounted(true); }, []);

  const filteredJobs = jobs.filter((job) =>
    job.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
    job.location.toLowerCase().includes(searchTerm.toLowerCase()),
  );

  const handleAddSkill = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && skillInput.trim()) {
      e.preventDefault();
      if (!newJob.requiredSkills.includes(skillInput.trim())) {
        setNewJob((prev) => ({ ...prev, requiredSkills: [...prev.requiredSkills, skillInput.trim()] }));
      }
      setSkillInput("");
    }
  };

  const handleRemoveSkill = (skill: string) =>
    setNewJob((prev) => ({ ...prev, requiredSkills: prev.requiredSkills.filter((s) => s !== skill) }));

  const updateQuestion = (id: string, patch: Partial<ApplicationQuestion>) =>
    setQuestions((qs) => qs.map((q) => (q.id === id ? { ...q, ...patch } : q)));

  const removeQuestion = (id: string) => setQuestions((qs) => qs.filter((q) => q.id !== id));

  const moveQuestion = (id: string, dir: -1 | 1) =>
    setQuestions((qs) => {
      const i = qs.findIndex((q) => q.id === id);
      if (i < 0) return qs;
      const j = i + dir;
      if (j < 0 || j >= qs.length) return qs;
      const copy = [...qs];
      [copy[i], copy[j]] = [copy[j], copy[i]];
      return copy;
    });

  const updateOption = (id: string, idx: number, value: string) =>
    setQuestions((qs) =>
      qs.map((q) => {
        if (q.id !== id) return q;
        const opts = [...(q.options || [])];
        opts[idx] = value;
        return { ...q, options: opts };
      }),
    );

  const addOption = (id: string) =>
    setQuestions((qs) => qs.map((q) => (q.id === id ? { ...q, options: [...(q.options || []), ""] } : q)));

  const removeOption = (id: string, idx: number) =>
    setQuestions((qs) =>
      qs.map((q) => (q.id === id ? { ...q, options: (q.options || []).filter((_, i) => i !== idx) } : q)),
    );

  const handleCreateJob = async () => {
    if (!newJob.title || !newJob.description || !newJob.location) {
      toast({ title: "Missing required fields", description: "Title, description and location are required.", variant: "destructive" });
      return;
    }
    const salaryMin = parseInt(newJob.salaryMin) || 0;
    const salaryMax = parseInt(newJob.salaryMax) || 0;
    if (salaryMax && salaryMin && salaryMax <= salaryMin) {
      toast({ title: "Invalid salary range", description: "Maximum salary must be greater than minimum salary.", variant: "destructive" });
      return;
    }
    for (const q of questions) {
      if (!q.label.trim()) {
        toast({ title: "Question label missing", description: "Every custom question needs a label.", variant: "destructive" });
        return;
      }
      if (q.type === "select" && (!q.options || q.options.filter((o) => o.trim()).length < 2)) {
        toast({ title: "Multiple-choice options", description: q.label + " needs at least 2 options.", variant: "destructive" });
        return;
      }
      if ((q.type === "text" || q.type === "textarea") && q.min_length != null && q.max_length != null && q.max_length < q.min_length) {
        toast({ title: "Invalid character limits", description: q.label + " - max length must be >= min length.", variant: "destructive" });
        return;
      }
    }

    try {
      setCreating(true);
      const cleanedQuestions = questions.map((q) => ({
        id: q.id,
        label: q.label.trim(),
        help_text: q.help_text || undefined,
        type: q.type,
        required: q.required,
        min_length: q.type === "text" || q.type === "textarea" ? q.min_length ?? null : null,
        max_length: q.type === "text" || q.type === "textarea" ? q.max_length ?? null : null,
        min_value: q.type === "number" ? q.min_value ?? null : null,
        max_value: q.type === "number" ? q.max_value ?? null : null,
        options: q.type === "select" ? (q.options || []).map((o) => o.trim()).filter(Boolean) : undefined,
      }));

      const jobData: Record<string, unknown> = {
        title: newJob.title,
        description: newJob.description,
        location: newJob.location,
        type: newJob.type,
        salary_min: salaryMin || null,
        salary_max: salaryMax || null,
        required_skills: newJob.requiredSkills,
        experience_level: newJob.experienceLevel,
        application_questions: cleanedQuestions,
      };
      if (newJob.last_date_to_apply) {
        jobData.last_date_to_apply = new Date(newJob.last_date_to_apply).toISOString();
      }

      await api.post("/job", jobData);

      setNewJob({
        title: "", description: "", type: "Remote", location: "",
        experienceLevel: "Mid-level", salaryMin: "", salaryMax: "",
        requiredSkills: [], status: "Draft", last_date_to_apply: "",
      });
      setQuestions([]);
      setIsDialogOpen(false);
      toast({ title: "Job created", description: "Your posting is live." });
      await fetchJobs();
    } catch (error) {
      console.error("Failed to create job:", error);
      toast({ title: "Error", description: "Failed to create job. Please try again.", variant: "destructive" });
    } finally {
      setCreating(false);
    }
  };

  const getStatusBadge = (status: Job["status"]) => {
    switch (status) {
      case "Open":
        return <Badge className="bg-success/15 text-success border-success/25">Open</Badge>;
      case "Closed":
        return <Badge variant="secondary">Closed</Badge>;
      case "Draft":
        return <Badge variant="outline">Draft</Badge>;
    }
  };

  if (!mounted) {
    return (
      <RecruiterLayout>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Jobs Management</h1>
              <p className="text-muted-foreground mt-1">Create and manage your job postings</p>
            </div>
          </div>
          <div className="flex items-center justify-center py-8"><Loader2 className="w-6 h-6 animate-spin" /></div>
        </div>
      </RecruiterLayout>
    );
  }

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Jobs Management</h1>
            <p className="text-muted-foreground mt-1">Create and manage your job postings</p>
          </div>
          <Dialog open={isDialogOpen} onOpenChange={setIsDialogOpen}>
            <DialogTrigger asChild>
              <Button><Plus className="w-4 h-4 mr-2" />Create New Job</Button>
            </DialogTrigger>
            <DialogContent className="max-w-3xl bg-card max-h-[90vh] overflow-y-auto p-0 gap-0">
              <div className="sticky top-0 z-10 bg-card border-b border-border px-6 py-4">
                <DialogHeader>
                  <DialogTitle className="flex items-center gap-2 text-xl">
                    <Briefcase className="w-5 h-5 text-primary" />Create New Job
                  </DialogTitle>
                  <p className="text-sm text-muted-foreground mt-1">
                    Build a structured posting and tailor the application form to your needs.
                  </p>
                </DialogHeader>
              </div>

              <div className="px-6 py-5 space-y-8">
                <section>
                  <SectionHeader icon={<FileText className="w-4 h-4" />} title="Basic Information" />
                  <div className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="title">Job Title <span className="text-destructive">*</span></Label>
                      <Input id="title" placeholder="e.g., Senior Frontend Developer" value={newJob.title}
                        onChange={(e) => setNewJob((prev) => ({ ...prev, title: e.target.value }))}
                        className="bg-background" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="description">Description <span className="text-destructive">*</span></Label>
                      <Textarea id="description" placeholder="Role overview, responsibilities, and what success looks like..."
                        value={newJob.description}
                        onChange={(e) => setNewJob((prev) => ({ ...prev, description: e.target.value }))}
                        rows={5} className="bg-background" />
                    </div>
                  </div>
                </section>

                <hr className="border-border" />

                <section>
                  <SectionHeader icon={<Briefcase className="w-4 h-4" />} title="Job Details" />
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="type">Work Mode</Label>
                      <Select value={newJob.type} onValueChange={(v) => setNewJob((prev) => ({ ...prev, type: v as Job["type"] }))}>
                        <SelectTrigger className="bg-background"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-popover">
                          <SelectItem value="Remote">Remote</SelectItem>
                          <SelectItem value="Onsite">Onsite</SelectItem>
                          <SelectItem value="Hybrid">Hybrid</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="location">Location <span className="text-destructive">*</span></Label>
                      <Input id="location" placeholder="e.g., San Francisco, CA" value={newJob.location}
                        onChange={(e) => setNewJob((prev) => ({ ...prev, location: e.target.value }))}
                        className="bg-background" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="experience">Experience Level</Label>
                      <Select value={newJob.experienceLevel}
                        onValueChange={(v) => setNewJob((prev) => ({ ...prev, experienceLevel: v as Job["experienceLevel"] }))}>
                        <SelectTrigger className="bg-background"><SelectValue /></SelectTrigger>
                        <SelectContent className="bg-popover">
                          <SelectItem value="Junior">Junior</SelectItem>
                          <SelectItem value="Mid-level">Mid-level</SelectItem>
                          <SelectItem value="Senior">Senior</SelectItem>
                          <SelectItem value="Lead">Lead</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="last_date">Application Deadline</Label>
                      <Input id="last_date" type="date" value={newJob.last_date_to_apply}
                        onChange={(e) => setNewJob((prev) => ({ ...prev, last_date_to_apply: e.target.value }))}
                        className="bg-background" />
                    </div>
                  </div>
                </section>

                <hr className="border-border" />

                <section>
                  <SectionHeader icon={<DollarSign className="w-4 h-4" />} title="Compensation" optional />
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label htmlFor="salaryMin">Min Salary ($/yr)</Label>
                      <Input id="salaryMin" type="number" placeholder="80000" value={newJob.salaryMin}
                        onChange={(e) => setNewJob((prev) => ({ ...prev, salaryMin: e.target.value }))}
                        className="bg-background" />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="salaryMax">Max Salary ($/yr)</Label>
                      <Input id="salaryMax" type="number" placeholder="120000" value={newJob.salaryMax}
                        onChange={(e) => setNewJob((prev) => ({ ...prev, salaryMax: e.target.value }))}
                        className="bg-background" />
                    </div>
                  </div>
                </section>

                <hr className="border-border" />

                <section>
                  <SectionHeader icon={<Sparkles className="w-4 h-4" />} title="Required Skills" />
                  <div className="space-y-2">
                    <Input id="skills" placeholder="Type a skill and press Enter" value={skillInput}
                      onChange={(e) => setSkillInput(e.target.value)} onKeyDown={handleAddSkill}
                      className="bg-background" />
                    {newJob.requiredSkills.length > 0 && (
                      <div className="flex flex-wrap gap-2 mt-2">
                        {newJob.requiredSkills.map((skill) => (
                          <Badge key={skill} variant="secondary" className="gap-1">
                            {skill}
                            <button onClick={() => handleRemoveSkill(skill)}><X className="w-3 h-3" /></button>
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </section>

                <hr className="border-border" />

                <section>
                  <div className="flex items-center justify-between mb-3">
                    <SectionHeader icon={<HelpCircle className="w-4 h-4" />} title="Custom Application Questions" optional noMargin />
                    <Button type="button" size="sm" variant="outline" onClick={() => setQuestions((qs) => [...qs, newQuestion()])}>
                      <Plus className="w-3 h-3 mr-1" /> Add Question
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mb-4">
                    Ask candidates anything specific to this role: short text, paragraphs, numbers, dates, multiple choice, yes/no, email or URL.
                  </p>

                  {questions.length === 0 ? (
                    <div className="border border-dashed border-border rounded-lg p-6 text-center text-sm text-muted-foreground">
                      No custom questions yet. Click <strong>Add Question</strong> to ask something like &quot;Why do you want to join us?&quot;
                    </div>
                  ) : (
                    <div className="space-y-4">
                      {questions.map((q, idx) => (
                        <div key={q.id} className="relative border border-border rounded-lg bg-background p-4 space-y-3">
                          <div className="flex items-center justify-between">
                            <div className="flex items-center gap-2 text-xs text-muted-foreground">
                              <GripVertical className="w-3 h-3" />Question {idx + 1}
                            </div>
                            <div className="flex items-center gap-1">
                              <Button type="button" variant="ghost" size="icon" className="h-7 w-7"
                                disabled={idx === 0} onClick={() => moveQuestion(q.id, -1)}>up</Button>
                              <Button type="button" variant="ghost" size="icon" className="h-7 w-7"
                                disabled={idx === questions.length - 1} onClick={() => moveQuestion(q.id, 1)}>dn</Button>
                              <Button type="button" variant="ghost" size="icon"
                                className="h-7 w-7 text-destructive hover:text-destructive"
                                onClick={() => removeQuestion(q.id)}>
                                <Trash2 className="w-3.5 h-3.5" />
                              </Button>
                            </div>
                          </div>

                          <div className="space-y-2">
                            <Label className="text-xs">Question</Label>
                            <Input placeholder="e.g., Why do you want to join XYZ?" value={q.label}
                              onChange={(e) => updateQuestion(q.id, { label: e.target.value })} className="bg-card" />
                          </div>

                          <div className="grid grid-cols-2 gap-3">
                            <div className="space-y-2">
                              <Label className="text-xs">Response Type</Label>
                              <Select value={q.type}
                                onValueChange={(v) => updateQuestion(q.id, {
                                  type: v as QuestionType,
                                  options: v === "select" ? q.options || ["", ""] : q.options,
                                })}>
                                <SelectTrigger className="bg-card"><SelectValue /></SelectTrigger>
                                <SelectContent className="bg-popover">
                                  {(Object.keys(QUESTION_TYPE_LABELS) as QuestionType[]).map((t) => (
                                    <SelectItem key={t} value={t}>{QUESTION_TYPE_LABELS[t]}</SelectItem>
                                  ))}
                                </SelectContent>
                              </Select>
                            </div>
                            <div className="space-y-2">
                              <Label className="text-xs">Required</Label>
                              <div className="flex items-center gap-2 h-10 px-3 rounded-md border border-input bg-card">
                                <Switch checked={q.required} onCheckedChange={(v) => updateQuestion(q.id, { required: v })} />
                                <span className="text-sm text-muted-foreground">{q.required ? "Answer required" : "Optional"}</span>
                              </div>
                            </div>
                          </div>

                          {(q.type === "text" || q.type === "textarea") && (
                            <div className="grid grid-cols-2 gap-3">
                              <div className="space-y-2">
                                <Label className="text-xs">Min Length (chars)</Label>
                                <Input type="number" min={0} placeholder="e.g., 50" value={q.min_length ?? ""}
                                  onChange={(e) => updateQuestion(q.id, { min_length: e.target.value === "" ? null : Number(e.target.value) })}
                                  className="bg-card" />
                              </div>
                              <div className="space-y-2">
                                <Label className="text-xs">Max Length (chars)</Label>
                                <Input type="number" min={0} placeholder="e.g., 500" value={q.max_length ?? ""}
                                  onChange={(e) => updateQuestion(q.id, { max_length: e.target.value === "" ? null : Number(e.target.value) })}
                                  className="bg-card" />
                              </div>
                            </div>
                          )}

                          {q.type === "number" && (
                            <div className="grid grid-cols-2 gap-3">
                              <div className="space-y-2">
                                <Label className="text-xs">Min Value</Label>
                                <Input type="number" placeholder="e.g., 0" value={q.min_value ?? ""}
                                  onChange={(e) => updateQuestion(q.id, { min_value: e.target.value === "" ? null : Number(e.target.value) })}
                                  className="bg-card" />
                              </div>
                              <div className="space-y-2">
                                <Label className="text-xs">Max Value</Label>
                                <Input type="number" placeholder="e.g., 100" value={q.max_value ?? ""}
                                  onChange={(e) => updateQuestion(q.id, { max_value: e.target.value === "" ? null : Number(e.target.value) })}
                                  className="bg-card" />
                              </div>
                            </div>
                          )}

                          {q.type === "select" && (
                            <div className="space-y-2">
                              <Label className="text-xs">Options</Label>
                              <div className="space-y-2">
                                {(q.options || []).map((opt, oi) => (
                                  <div key={oi} className="flex gap-2">
                                    <Input placeholder={"Option " + (oi + 1)} value={opt}
                                      onChange={(e) => updateOption(q.id, oi, e.target.value)} className="bg-card" />
                                    <Button type="button" variant="ghost" size="icon"
                                      className="h-10 w-10 text-destructive"
                                      onClick={() => removeOption(q.id, oi)}
                                      disabled={(q.options || []).length <= 1}>
                                      <X className="w-4 h-4" />
                                    </Button>
                                  </div>
                                ))}
                                <Button type="button" variant="outline" size="sm" onClick={() => addOption(q.id)}>
                                  <Plus className="w-3 h-3 mr-1" /> Add Option
                                </Button>
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </section>

                <div className="flex justify-end gap-3 pt-4 border-t border-border sticky bottom-0 bg-card pb-2 -mx-6 px-6">
                  <Button variant="outline" onClick={() => setIsDialogOpen(false)}>Cancel</Button>
                  <Button onClick={handleCreateJob} disabled={creating} className="min-w-[140px]">
                    {creating ? (<><Loader2 className="w-4 h-4 mr-2 animate-spin" />Creating...</>) : "Create Job"}
                  </Button>
                </div>
              </div>
            </DialogContent>
          </Dialog>
        </div>

        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input placeholder="Search jobs..." value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)} className="pl-10 bg-card" />
        </div>

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
                  <TableRow><TableCell colSpan={5} className="text-center py-8">
                    <div className="flex items-center justify-center gap-2"><Loader2 className="w-4 h-4 animate-spin" />Loading jobs...</div>
                  </TableCell></TableRow>
                ) : filteredJobs.length === 0 ? (
                  <TableRow><TableCell colSpan={5} className="text-center py-8 text-muted-foreground">
                    No jobs found. Create your first job posting.
                  </TableCell></TableRow>
                ) : (
                  filteredJobs.map((job) => (
                    <TableRow key={job.id}>
                      <TableCell><div>
                        <p className="font-medium">{job.title}</p>
                        <p className="text-sm text-muted-foreground">{job.location} - {job.type}</p>
                      </div></TableCell>
                      <TableCell>{format(parseISO(job.createdAt), "MMM d, yyyy")}</TableCell>
                      <TableCell>{job.applicants}</TableCell>
                      <TableCell>{getStatusBadge(job.status)}</TableCell>
                      <TableCell className="text-right">
                        <div className="flex items-center justify-end gap-2">
                          <Button variant="ghost" size="icon" asChild>
                            <Link href={"/recruiter/job/" + job.id}><Eye className="w-4 h-4" /></Link>
                          </Button>
                          <Button variant="ghost" size="icon"><Edit className="w-4 h-4" /></Button>
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

function SectionHeader({ icon, title, optional, noMargin }: {
  icon: React.ReactNode; title: string; optional?: boolean; noMargin?: boolean;
}) {
  return (
    <div className={"flex items-center gap-2 " + (noMargin ? "" : "mb-4")}>
      <div className="p-1.5 rounded-md bg-accent text-accent-foreground">{icon}</div>
      <h3 className="font-semibold text-foreground">{title}</h3>
      {optional && <span className="text-xs text-muted-foreground">(optional)</span>}
    </div>
  );
}
