'use client';

import { useState } from 'react';
import { CandidateLayout } from '@/components/layout/CandidateLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { useAuth } from '@/contexts/AuthContext';
import { Upload, Linkedin, FileText, X, Plus } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

export default function Profile() {
  const { user } = useAuth();
  const { toast } = useToast();
  const [bio, setBio] = useState('');
  const [linkedin, setLinkedin] = useState('');
  const [skills, setSkills] = useState<string[]>(['React', 'TypeScript', 'Node.js']);
  const [skillInput, setSkillInput] = useState('');
  const [resumeUploaded, setResumeUploaded] = useState(false);

  const handleAddSkill = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' && skillInput.trim()) {
      e.preventDefault();
      if (!skills.includes(skillInput.trim())) {
        setSkills(prev => [...prev, skillInput.trim()]);
      }
      setSkillInput('');
    }
  };

  const handleRemoveSkill = (skill: string) => {
    setSkills(prev => prev.filter(s => s !== skill));
  };

  const handleSave = () => {
    toast({
      title: 'Profile updated',
      description: 'Your changes have been saved successfully.',
    });
  };

  const handleResumeUpload = () => {
    setResumeUploaded(true);
    toast({
      title: 'Resume uploaded',
      description: 'Your resume has been uploaded successfully.',
    });
  };

  return (
    <CandidateLayout>
      <div className="max-w-3xl mx-auto space-y-6">
        <div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">My Profile</h1>
          <p className="text-muted-foreground mt-1">Complete your profile to apply for jobs quickly</p>
        </div>

        {/* Profile Header */}
        <Card className="bg-card border-border">
          <CardContent className="p-6">
            <div className="flex items-center gap-6">
              <Avatar className="w-24 h-24">
                <AvatarFallback className="bg-primary text-primary-foreground text-3xl">
                  {user?.name?.charAt(0).toUpperCase() || 'U'}
                </AvatarFallback>
              </Avatar>
              <div className="flex-1">
                <h2 className="text-3xl font-extrabold tracking-tight text-foreground">{user?.name}</h2>
                <p className="text-muted-foreground mt-1">{user?.email}</p>
                <div className="mt-3">
                  <Button variant="outline" size="sm">
                    <Upload className="w-4 h-4 mr-2" />
                    Change Photo
                  </Button>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Resume Upload */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              Resume
            </CardTitle>
            <CardDescription>Upload your resume to apply for jobs quickly</CardDescription>
          </CardHeader>
          <CardContent>
            {resumeUploaded ? (
              <div className="flex items-center justify-between p-4 rounded-lg bg-primary/10 border border-primary/20">
                <div className="flex items-center gap-3">
                  <FileText className="w-8 h-8 text-primary" />
                  <div>
                    <p className="font-medium">resume.pdf</p>
                    <p className="text-sm text-muted-foreground">Uploaded just now</p>
                  </div>
                </div>
                <Button variant="outline" size="sm" onClick={() => setResumeUploaded(false)}>
                  Replace
                </Button>
              </div>
            ) : (
              <div 
                className="border-2 border-dashed border-border rounded-lg p-8 text-center cursor-pointer hover:border-primary/50 transition-colors"
                onClick={handleResumeUpload}
              >
                <Upload className="w-12 h-12 mx-auto text-muted-foreground mb-4" />
                <p className="text-foreground font-medium">Click to upload your resume</p>
                <p className="text-sm text-muted-foreground mt-1">PDF or DOCX, max 5MB</p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* About */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>About</CardTitle>
            <CardDescription>Tell employers about yourself</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="bio">Bio</Label>
              <Textarea
                id="bio"
                placeholder="Write a brief description about yourself, your experience, and what you're looking for..."
                value={bio}
                onChange={(e) => setBio(e.target.value)}
                rows={4}
                className="bg-background"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="linkedin">LinkedIn Profile</Label>
              <div className="relative">
                <Linkedin className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  id="linkedin"
                  placeholder="https://linkedin.com/in/yourprofile"
                  value={linkedin}
                  onChange={(e) => setLinkedin(e.target.value)}
                  className="pl-10 bg-background"
                />
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Skills */}
        <Card className="bg-card border-border">
          <CardHeader>
            <CardTitle>Skills</CardTitle>
            <CardDescription>Add your professional skills</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="relative">
              <Plus className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Type a skill and press Enter"
                value={skillInput}
                onChange={(e) => setSkillInput(e.target.value)}
                onKeyDown={handleAddSkill}
                className="pl-10 bg-background"
              />
            </div>
            
            {skills.length > 0 && (
              <div className="flex flex-wrap gap-2">
                {skills.map((skill) => (
                  <Badge key={skill} variant="secondary" className="gap-1 py-1.5 px-3">
                    {skill}
                    <button onClick={() => handleRemoveSkill(skill)} className="ml-1">
                      <X className="w-3 h-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        <Button onClick={handleSave} className="w-full">
          Save Profile
        </Button>
      </div>
    </CandidateLayout>
  );
}

