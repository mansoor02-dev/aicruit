'use client';

import { useState, useRef } from 'react';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { useToast } from '@/hooks/use-toast';
import {
  Upload, Loader2, CheckCircle, Plus, X, User, GraduationCap,
  Briefcase, FolderOpen, Sparkles, FileText, ArrowLeft, Send
} from 'lucide-react';
import { api, getAuthToken } from '@/lib/api';

type ApplicationQuestionType =
  | "text"
  | "textarea"
  | "number"
  | "date"
  | "select"
  | "yes_no"
  | "email"
  | "url";

export interface ApplicationQuestion {
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

interface ApplyJobModalProps {
  jobId: string;
  jobTitle: string;
  isOpen: boolean;
  onClose: () => void;
  onApplySuccess: () => void;
  applicationQuestions?: ApplicationQuestion[];
}

interface Education {
  university: string;
  degree: string;
  field: string;
  start_year: string;
  end_year: string;
}

interface Experience {
  title: string;
  company: string;
  start_date: string;
  end_date: string;
  description: string;
}

interface Project {
  title: string;
  description: string;
}

interface ParsedData {
  name: string;
  email: string;
  phone: string;
  location: string;
  summary: string;
  skills: string[];
  education: Education[];
  experience: Experience[];
  projects: Project[];
}

const emptyEducation: Education = { university: '', degree: '', field: '', start_year: '', end_year: '' };
const emptyExperience: Experience = { title: '', company: '', start_date: '', end_date: '', description: '' };
const emptyProject: Project = { title: '', description: '' };

export function ApplyJobModal({ jobId, jobTitle, isOpen, onClose, onApplySuccess, applicationQuestions = [] }: ApplyJobModalProps) {
  const [step, setStep] = useState<'upload' | 'form'>('upload');
  const [resumeId, setResumeId] = useState<string | null>(null);
  const [isParsing, setIsParsing] = useState(false);
  const [isApplying, setIsApplying] = useState(false);
  const [fileName, setFileName] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const dragAreaRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();

  // Form state
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [phone, setPhone] = useState('');
  const [location, setLocation] = useState('');
  const [education, setEducation] = useState<Education[]>([{ ...emptyEducation }]);
  const [experience, setExperience] = useState<Experience[]>([{ ...emptyExperience }]);
  const [projects, setProjects] = useState<Project[]>([{ ...emptyProject }]);
  const [skills, setSkills] = useState<string[]>([]);
  const [newSkill, setNewSkill] = useState('');
  // ── Recruiter-defined custom question answers, keyed by question id ──
  const [answers, setAnswers] = useState<Record<string, string | number | boolean | null>>({});
  const updateAnswer = (qid: string, value: string | number | boolean | null) =>
    setAnswers((prev) => ({ ...prev, [qid]: value }));

  const resetForm = () => {
    setStep('upload');
    setResumeId(null);
    setIsParsing(false);
    setIsApplying(false);
    setFileName('');
    setName(''); setEmail(''); setPhone(''); setLocation('');
    setEducation([{ ...emptyEducation }]);
    setExperience([{ ...emptyExperience }]);
    setProjects([{ ...emptyProject }]);
    setSkills([]); setNewSkill('');
    setAnswers({});
  };

  const handleClose = () => { resetForm(); onClose(); };

  const handleFileSelect = async (file: File) => {
    const ext = file.name.split('.').pop()?.toLowerCase();
    if (!['pdf', 'docx'].includes(ext || '')) {
      toast({ title: 'Invalid file', description: 'Please upload a PDF or DOCX file', variant: 'destructive' });
      return;
    }
    setFileName(file.name);
    setIsParsing(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const token = getAuthToken();
      const res = await fetch(`${API_BASE}/job/upload-resume`, {
        method: 'POST',
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }

      const result = await res.json();
      setResumeId(result.resume_id);

      if (result.parsed && result.data) {
        const d: ParsedData = result.data;
        setName(d.name || '');
        setEmail(d.email || '');
        setPhone(d.phone || '');
        setLocation(d.location || '');
        setSkills(d.skills || []);
        if (d.education?.length) {
          setEducation(d.education.map((e: any) => ({
            university: e.university || '', degree: e.degree || '',
            field: e.field || '', start_year: String(e.start_year || ''),
            end_year: String(e.end_year || ''),
          })));
        }
        if (d.experience?.length) {
          setExperience(d.experience.map((e: any) => ({
            title: e.title || '', company: e.company || '',
            start_date: e.start_date || '', end_date: e.end_date || '',
            description: e.description || '',
          })));
        }
        if (d.projects?.length) {
          setProjects(d.projects.map((p: any) => ({
            title: p.title || '', description: p.description || '',
          })));
        }
        toast({ title: 'Resume parsed!', description: 'Form auto-filled from your resume' });
      } else {
        toast({ title: 'Resume uploaded', description: 'Could not parse — please fill in manually' });
      }
      setStep('form');
    } catch (error: any) {
      toast({ title: 'Upload failed', description: error.message || 'Please try again', variant: 'destructive' });
      setFileName('');
    } finally {
      setIsParsing(false);
    }
  };

  const handleDragOver = (e: React.DragEvent) => { e.preventDefault(); dragAreaRef.current?.classList.add('border-primary', 'bg-primary/5'); };
  const handleDragLeave = (e: React.DragEvent) => { e.preventDefault(); dragAreaRef.current?.classList.remove('border-primary', 'bg-primary/5'); };
  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    dragAreaRef.current?.classList.remove('border-primary', 'bg-primary/5');
    if (e.dataTransfer.files.length > 0) handleFileSelect(e.dataTransfer.files[0]);
  };

  const addSkill = () => {
    const s = newSkill.trim();
    if (s && !skills.includes(s)) { setSkills([...skills, s]); setNewSkill(''); }
  };

  const handleApply = async () => {
    if (!resumeId) { toast({ title: 'Error', description: 'Resume not uploaded', variant: 'destructive' }); return; }
    if (!name || !email || !phone || !location) {
      toast({ title: 'Missing fields', description: 'Please fill all candidate details', variant: 'destructive' }); return;
    }
    // ── Validate custom application questions ──
    for (const q of applicationQuestions) {
      const v = answers[q.id];
      const isEmpty = v === undefined || v === null || (typeof v === 'string' && v.trim() === '');
      if (q.required && isEmpty) {
        toast({ title: 'Required answer missing', description: q.label, variant: 'destructive' });
        return;
      }
      if (typeof v === 'string' && (q.type === 'text' || q.type === 'textarea')) {
        const len = v.length;
        if (q.min_length != null && len < q.min_length) {
          toast({ title: 'Answer too short', description: q.label + ' needs at least ' + q.min_length + ' characters.', variant: 'destructive' });
          return;
        }
        if (q.max_length != null && len > q.max_length) {
          toast({ title: 'Answer too long', description: q.label + ' allows at most ' + q.max_length + ' characters.', variant: 'destructive' });
          return;
        }
      }
      if (typeof v === 'number' && q.type === 'number') {
        if (q.min_value != null && v < q.min_value) {
          toast({ title: 'Value too small', description: q.label + ' must be at least ' + q.min_value + '.', variant: 'destructive' });
          return;
        }
        if (q.max_value != null && v > q.max_value) {
          toast({ title: 'Value too large', description: q.label + ' must be at most ' + q.max_value + '.', variant: 'destructive' });
          return;
        }
      }
    }
    const questionResponses = applicationQuestions.map((q) => ({
      question_id: q.id,
      label: q.label,
      type: q.type,
      value: answers[q.id] ?? null,
    }));
    try {
      setIsApplying(true);
      await api.post('/job/apply', {
        job_id: jobId,
        resume_id: resumeId,
        applicant_name: name,
        applicant_email: email,
        applicant_phone: phone,
        applicant_location: location,
        summary: '',
        skills: skills,
        education: education,
        experience: experience,
        projects: projects,
        question_responses: questionResponses,
      });
      toast({ title: 'Application submitted!', description: 'Your application has been sent successfully' });
      onApplySuccess();
      handleClose();
    } catch (error: any) {
      toast({ title: 'Failed', description: error.message || 'Could not submit application', variant: 'destructive' });
    } finally { setIsApplying(false); }
  };

  const updateEducation = (i: number, field: keyof Education, val: string) => {
    const arr = [...education]; arr[i] = { ...arr[i], [field]: val }; setEducation(arr);
  };
  const updateExperience = (i: number, field: keyof Experience, val: string) => {
    const arr = [...experience]; arr[i] = { ...arr[i], [field]: val }; setExperience(arr);
  };
  const updateProject = (i: number, field: keyof Project, val: string) => {
    const arr = [...projects]; arr[i] = { ...arr[i], [field]: val }; setProjects(arr);
  };

  return (
    <Dialog open={isOpen} onOpenChange={handleClose}>
      <DialogContent className="sm:max-w-3xl max-h-[90vh] overflow-y-auto p-0 gap-0 bg-card">
        {/* Header */}
        <div className="sticky top-0 z-10 bg-card border-b border-border px-6 py-4">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-xl">
              {step === 'form' && (
                <Button variant="ghost" size="sm" className="h-8 w-8 p-0 mr-1" onClick={() => { resetForm(); }}>
                  <ArrowLeft className="w-4 h-4" />
                </Button>
              )}
              <Briefcase className="w-5 h-5 text-primary" />
              Apply to {jobTitle}
            </DialogTitle>
          </DialogHeader>
        </div>

        <div className="px-6 py-5">
          {/* ========== STEP 1: UPLOAD ========== */}
          {step === 'upload' && (
            <div className="flex flex-col items-center py-8">
              {isParsing ? (
                <div className="flex flex-col items-center gap-4 animate-pulse">
                  <div className="relative">
                    <div className="w-20 h-20 rounded-full bg-primary/10 flex items-center justify-center">
                      <Loader2 className="w-10 h-10 text-primary animate-spin" />
                    </div>
                    <div className="absolute -bottom-1 -right-1 w-7 h-7 rounded-full bg-primary flex items-center justify-center">
                      <Sparkles className="w-4 h-4 text-primary-foreground" />
                    </div>
                  </div>
                  <div className="text-center space-y-1">
                    <p className="font-semibold text-foreground">Analyzing your resume...</p>
                    <p className="text-sm text-muted-foreground">{fileName}</p>
                    <p className="text-xs text-muted-foreground">This may take a few seconds</p>
                  </div>
                </div>
              ) : (
                <div
                  ref={dragAreaRef}
                  onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
                  onClick={() => fileInputRef.current?.click()}
                  className="w-full border-2 border-dashed border-muted-foreground/30 rounded-xl p-12 text-center hover:border-primary/50 transition-all cursor-pointer group"
                >
                  <div className="w-16 h-16 mx-auto mb-4 rounded-full bg-primary/10 flex items-center justify-center group-hover:bg-primary/20 transition-colors">
                    <Upload className="w-8 h-8 text-primary" />
                  </div>
                  <p className="text-base font-semibold text-foreground mb-1">Drag & drop your resume</p>
                  <p className="text-sm text-muted-foreground mb-3">or click to browse files</p>
                  <Badge variant="outline" className="text-xs">PDF, DOCX — Max 10MB</Badge>
                  <input ref={fileInputRef} type="file" accept=".pdf,.docx" className="hidden"
                    onChange={(e) => { if (e.target.files?.[0]) handleFileSelect(e.target.files[0]); }} />
                </div>
              )}
            </div>
          )}

          {/* ========== STEP 2: FORM ========== */}
          {step === 'form' && (
            <div className="space-y-8">
              {/* Resume badge */}
              <div className="flex items-center gap-2 p-3 bg-accent/50 rounded-lg border border-border">
                <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
                <FileText className="w-4 h-4 text-muted-foreground shrink-0" />
                <span className="text-sm font-medium truncate flex-1">{fileName}</span>
                <Badge variant="secondary" className="text-xs shrink-0">Parsed</Badge>
              </div>

              {/* --- Candidate Details --- */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <div className="p-1.5 rounded-md bg-primary/10"><User className="w-4 h-4 text-primary" /></div>
                  <h3 className="font-semibold text-foreground">Candidate Details</h3>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div><Label htmlFor="name">Full Name <span className="text-destructive">*</span></Label>
                    <Input id="name" value={name} onChange={e => setName(e.target.value)} placeholder="John Doe" className="mt-1 bg-background" required /></div>
                  <div><Label htmlFor="email">Email <span className="text-destructive">*</span></Label>
                    <Input id="email" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="john@example.com" className="mt-1 bg-background" required /></div>
                  <div><Label htmlFor="phone">Phone <span className="text-destructive">*</span></Label>
                    <Input id="phone" value={phone} onChange={e => setPhone(e.target.value)} placeholder="+1 234 567 890" className="mt-1 bg-background" required /></div>
                  <div><Label htmlFor="location">Location <span className="text-destructive">*</span></Label>
                    <Input id="location" value={location} onChange={e => setLocation(e.target.value)} placeholder="City, Country" className="mt-1 bg-background" required /></div>
                </div>
              </section>

              <hr className="border-border" />

              {/* --- Education --- */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-md bg-primary/10"><GraduationCap className="w-4 h-4 text-primary" /></div>
                    <h3 className="font-semibold text-foreground">Education</h3>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setEducation([...education, { ...emptyEducation }])}>
                    <Plus className="w-3 h-3 mr-1" />Add
                  </Button>
                </div>
                <div className="space-y-4">
                  {education.map((edu, i) => (
                    <div key={i} className="relative p-4 border border-border rounded-lg bg-background space-y-3">
                      {education.length > 1 && (
                        <button className="absolute top-2 right-2 text-muted-foreground hover:text-destructive" onClick={() => setEducation(education.filter((_, j) => j !== i))}>
                          <X className="w-4 h-4" /></button>
                      )}
                      <div><Label>Institute <span className="text-destructive">*</span></Label>
                        <Input value={edu.university} onChange={e => updateEducation(i, 'university', e.target.value)} placeholder="University name" className="mt-1" required /></div>
                      <div className="grid grid-cols-2 gap-3">
                        <div><Label>Degree <span className="text-destructive">*</span></Label>
                          <Input value={edu.degree} onChange={e => updateEducation(i, 'degree', e.target.value)} placeholder="Bachelor's" className="mt-1" required /></div>
                        <div><Label>Field <span className="text-destructive">*</span></Label>
                          <Input value={edu.field} onChange={e => updateEducation(i, 'field', e.target.value)} placeholder="Computer Science" className="mt-1" required /></div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div><Label>Start Year <span className="text-destructive">*</span></Label>
                          <Input value={edu.start_year} onChange={e => updateEducation(i, 'start_year', e.target.value)} placeholder="2020" className="mt-1" required /></div>
                        <div><Label>End Year <span className="text-destructive">*</span></Label>
                          <Input value={edu.end_year} onChange={e => updateEducation(i, 'end_year', e.target.value)} placeholder="2024" className="mt-1" required /></div>
                      </div>
                    </div>
                  ))}
                </div>
              </section>

              <hr className="border-border" />

              {/* --- Experience --- */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-md bg-primary/10"><Briefcase className="w-4 h-4 text-primary" /></div>
                    <h3 className="font-semibold text-foreground">Experience</h3>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setExperience([...experience, { ...emptyExperience }])}>
                    <Plus className="w-3 h-3 mr-1" />Add
                  </Button>
                </div>
                <div className="space-y-4">
                  {experience.map((exp, i) => (
                    <div key={i} className="relative p-4 border border-border rounded-lg bg-background space-y-3">
                      {experience.length > 1 && (
                        <button className="absolute top-2 right-2 text-muted-foreground hover:text-destructive" onClick={() => setExperience(experience.filter((_, j) => j !== i))}>
                          <X className="w-4 h-4" /></button>
                      )}
                      <div className="grid grid-cols-2 gap-3">
                        <div><Label>Title <span className="text-destructive">*</span></Label>
                          <Input value={exp.title} onChange={e => updateExperience(i, 'title', e.target.value)} placeholder="Software Engineer" className="mt-1" required /></div>
                        <div><Label>Company <span className="text-destructive">*</span></Label>
                          <Input value={exp.company} onChange={e => updateExperience(i, 'company', e.target.value)} placeholder="Company name" className="mt-1" required /></div>
                      </div>
                      <div className="grid grid-cols-2 gap-3">
                        <div><Label>Start Date <span className="text-destructive">*</span></Label>
                          <Input value={exp.start_date} onChange={e => updateExperience(i, 'start_date', e.target.value)} placeholder="2023-01" className="mt-1" required /></div>
                        <div><Label>End Date <span className="text-destructive">*</span></Label>
                          <Input value={exp.end_date} onChange={e => updateExperience(i, 'end_date', e.target.value)} placeholder="Present" className="mt-1" required /></div>
                      </div>
                      <div><Label>Description <span className="text-destructive">*</span></Label>
                        <Textarea value={exp.description} onChange={e => updateExperience(i, 'description', e.target.value)} placeholder="What did you do?" className="mt-1" required /></div>
                    </div>
                  ))}
                </div>
              </section>

              <hr className="border-border" />

              {/* --- Projects --- */}
              <section>
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-2">
                    <div className="p-1.5 rounded-md bg-primary/10"><FolderOpen className="w-4 h-4 text-primary" /></div>
                    <h3 className="font-semibold text-foreground">Projects</h3>
                  </div>
                  <Button variant="outline" size="sm" onClick={() => setProjects([...projects, { ...emptyProject }])}>
                    <Plus className="w-3 h-3 mr-1" />Add
                  </Button>
                </div>
                <div className="space-y-4">
                  {projects.map((proj, i) => (
                    <div key={i} className="relative p-4 border border-border rounded-lg bg-background space-y-3">
                      {projects.length > 1 && (
                        <button className="absolute top-2 right-2 text-muted-foreground hover:text-destructive" onClick={() => setProjects(projects.filter((_, j) => j !== i))}>
                          <X className="w-4 h-4" /></button>
                      )}
                      <div><Label>Title <span className="text-destructive">*</span></Label>
                        <Input value={proj.title} onChange={e => updateProject(i, 'title', e.target.value)} placeholder="Project name" className="mt-1" required /></div>
                      <div><Label>Description <span className="text-destructive">*</span></Label>
                        <Textarea value={proj.description} onChange={e => updateProject(i, 'description', e.target.value)} placeholder="What was the project about?" className="mt-1" required /></div>
                    </div>
                  ))}
                </div>
              </section>

              <hr className="border-border" />

              {/* --- Skills --- */}
              <section>
                <div className="flex items-center gap-2 mb-4">
                  <div className="p-1.5 rounded-md bg-primary/10"><Sparkles className="w-4 h-4 text-primary" /></div>
                  <h3 className="font-semibold text-foreground">Skills</h3>
                </div>
                <div className="flex flex-wrap gap-2 mb-3">
                  {skills.map((skill) => (
                    <Badge key={skill} variant="secondary" className="gap-1 pr-1.5 text-sm">
                      {skill}
                      <button onClick={() => setSkills(skills.filter(s => s !== skill))} className="ml-1 hover:text-destructive">
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                  {skills.length === 0 && <p className="text-sm text-muted-foreground">No skills added yet</p>}
                </div>
                <div className="flex gap-2">
                  <Input value={newSkill} onChange={e => setNewSkill(e.target.value)} placeholder="Add a skill..."
                    className="bg-background" onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); addSkill(); } }} />
                  <Button variant="outline" onClick={addSkill} disabled={!newSkill.trim()}>
                    <Plus className="w-4 h-4" />
                  </Button>
                </div>
              </section>

              {applicationQuestions.length > 0 && (
                <>
                  <hr className="border-border" />
                  <section>
                    <div className="flex items-center gap-2 mb-4">
                      <div className="p-1.5 rounded-md bg-primary/10"><FileText className="w-4 h-4 text-primary" /></div>
                      <h3 className="font-semibold text-foreground">Additional Questions</h3>
                    </div>
                    <div className="space-y-5">
                      {applicationQuestions.map((q) => (
                        <ApplicationQuestionField
                          key={q.id}
                          question={q}
                          value={answers[q.id] ?? (q.type === 'yes_no' ? null : '')}
                          onChange={(v) => updateAnswer(q.id, v)}
                        />
                      ))}
                    </div>
                  </section>
                </>
              )}

              {/* Submit */}
              <div className="flex justify-end gap-3 pt-4 border-t border-border">
                <Button variant="outline" onClick={handleClose}>Cancel</Button>
                <Button onClick={handleApply} disabled={isApplying} className="min-w-[140px]">
                  {isApplying ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <Send className="w-4 h-4 mr-2" />}
                  {isApplying ? 'Submitting...' : 'Apply Now'}
                </Button>
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}


// ─── ApplicationQuestionField ───────────────────────────────────────────────
// Renders one recruiter-defined question and reports its answer up.

function ApplicationQuestionField({
  question,
  value,
  onChange,
}: {
  question: ApplicationQuestion;
  value: string | number | boolean | null;
  onChange: (v: string | number | boolean | null) => void;
}) {
  const required = question.required;
  const labelEl = (
    <Label className="text-sm font-medium">
      {question.label}
      {required && <span className="text-destructive ml-1">*</span>}
    </Label>
  );

  const helpEl = question.help_text ? (
    <p className="text-xs text-muted-foreground mt-1">{question.help_text}</p>
  ) : null;

  // ── Text / Textarea (with character counter) ──
  if (question.type === 'text' || question.type === 'textarea') {
    const v = (value as string) ?? '';
    const len = v.length;
    const min = question.min_length ?? null;
    const max = question.max_length ?? null;
    const tooShort = min != null && len > 0 && len < min;
    const tooLong = max != null && len > max;
    const hint =
      min != null && max != null
        ? len + ' / ' + max + ' (min ' + min + ')'
        : max != null
        ? len + ' / ' + max
        : min != null
        ? len + ' (min ' + min + ')'
        : len + ' characters';

    return (
      <div className="space-y-1.5">
        {labelEl}
        {question.type === 'textarea' ? (
          <Textarea
            value={v}
            onChange={(e) => onChange(e.target.value)}
            maxLength={max ?? undefined}
            rows={4}
            className="bg-background"
          />
        ) : (
          <Input
            value={v}
            onChange={(e) => onChange(e.target.value)}
            maxLength={max ?? undefined}
            className="bg-background"
          />
        )}
        {helpEl}
        <div
          className={
            'text-xs ' +
            (tooLong || tooShort ? 'text-destructive' : 'text-muted-foreground')
          }
        >
          {hint}
        </div>
      </div>
    );
  }

  // ── Number ──
  if (question.type === 'number') {
    return (
      <div className="space-y-1.5">
        {labelEl}
        <Input
          type="number"
          value={value === null || value === undefined ? '' : String(value)}
          min={question.min_value ?? undefined}
          max={question.max_value ?? undefined}
          onChange={(e) => onChange(e.target.value === '' ? null : Number(e.target.value))}
          className="bg-background"
        />
        {helpEl}
      </div>
    );
  }

  // ── Date ──
  if (question.type === 'date') {
    return (
      <div className="space-y-1.5">
        {labelEl}
        <Input
          type="date"
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          className="bg-background"
        />
        {helpEl}
      </div>
    );
  }

  // ── Email / URL ──
  if (question.type === 'email' || question.type === 'url') {
    return (
      <div className="space-y-1.5">
        {labelEl}
        <Input
          type={question.type}
          value={(value as string) ?? ''}
          onChange={(e) => onChange(e.target.value)}
          placeholder={question.type === 'email' ? 'name@example.com' : 'https://example.com'}
          className="bg-background"
        />
        {helpEl}
      </div>
    );
  }

  // ── Select (multiple choice) ──
  if (question.type === 'select') {
    const v = (value as string) ?? '';
    return (
      <div className="space-y-1.5">
        {labelEl}
        <select
          value={v}
          onChange={(e) => onChange(e.target.value)}
          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
        >
          <option value="">Select an option</option>
          {(question.options || []).map((opt) => (
            <option key={opt} value={opt}>{opt}</option>
          ))}
        </select>
        {helpEl}
      </div>
    );
  }

  // ── Yes / No ──
  if (question.type === 'yes_no') {
    const v = value as boolean | null;
    return (
      <div className="space-y-1.5">
        {labelEl}
        <div className="flex gap-2">
          <Button
            type="button"
            variant={v === true ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange(true)}
          >
            Yes
          </Button>
          <Button
            type="button"
            variant={v === false ? 'default' : 'outline'}
            size="sm"
            onClick={() => onChange(false)}
          >
            No
          </Button>
        </div>
        {helpEl}
      </div>
    );
  }

  return null;
}
