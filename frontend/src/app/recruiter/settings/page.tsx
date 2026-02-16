'use client';

import { useState } from 'react';
import { RecruiterLayout } from '@/components/layout/RecruiterLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Building2, Users, CreditCard, Bell, Upload, Plus, Mail } from 'lucide-react';
import { useToast } from '@/hooks/use-toast';

export default function Settings() {
  const [companyName, setCompanyName] = useState('TechCorp Inc.');
  const [website, setWebsite] = useState('https://techcorp.com');
  const [description, setDescription] = useState('A leading technology company focused on innovation and excellence.');
  const [emailNotifications, setEmailNotifications] = useState(true);
  const [interviewNotifications, setInterviewNotifications] = useState(true);
  const { toast } = useToast();

  const teamMembers = [
    { id: '1', name: 'John Doe', email: 'john@techcorp.com', role: 'Admin' },
    { id: '2', name: 'Jane Smith', email: 'jane@techcorp.com', role: 'Recruiter' },
    { id: '3', name: 'Mike Johnson', email: 'mike@techcorp.com', role: 'Recruiter' },
  ];

  const handleSave = () => {
    toast({
      title: 'Settings saved',
      description: 'Your changes have been saved successfully.',
    });
  };

  return (
    <RecruiterLayout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-bold text-foreground">Settings</h1>
          <p className="text-muted-foreground">Manage your company profile and preferences</p>
        </div>

        <Tabs defaultValue="company" className="space-y-6">
          <TabsList className="bg-card border border-border">
            <TabsTrigger value="company" className="flex items-center gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Building2 className="w-4 h-4" />
              Company Profile
            </TabsTrigger>
            <TabsTrigger value="team" className="flex items-center gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Users className="w-4 h-4" />
              Team
            </TabsTrigger>
            <TabsTrigger value="billing" className="flex items-center gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <CreditCard className="w-4 h-4" />
              Billing
            </TabsTrigger>
            <TabsTrigger value="notifications" className="flex items-center gap-2 data-[state=active]:bg-primary data-[state=active]:text-primary-foreground">
              <Bell className="w-4 h-4" />
              Notifications
            </TabsTrigger>
          </TabsList>

          <TabsContent value="company">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Company Profile</CardTitle>
                <CardDescription>Update your company information and branding</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center gap-6">
                  <div className="w-24 h-24 rounded-xl bg-muted flex items-center justify-center border-2 border-dashed border-border">
                    <Upload className="w-8 h-8 text-muted-foreground" />
                  </div>
                  <div>
                    <Button variant="outline">Upload Logo</Button>
                    <p className="text-sm text-muted-foreground mt-2">
                      PNG, JPG up to 2MB. Recommended 400x400px
                    </p>
                  </div>
                </div>

                <div className="grid gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="company-name">Company Name</Label>
                    <Input
                      id="company-name"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      className="bg-background"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="website">Website</Label>
                    <Input
                      id="website"
                      value={website}
                      onChange={(e) => setWebsite(e.target.value)}
                      className="bg-background"
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="description">Description</Label>
                    <Textarea
                      id="description"
                      value={description}
                      onChange={(e) => setDescription(e.target.value)}
                      rows={4}
                      className="bg-background"
                    />
                  </div>
                </div>

                <Button onClick={handleSave}>Save Changes</Button>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="team">
            <Card className="bg-card border-border">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle>Team Management</CardTitle>
                  <CardDescription>Manage your recruitment team members</CardDescription>
                </div>
                <Button>
                  <Plus className="w-4 h-4 mr-2" />
                  Invite Member
                </Button>
              </CardHeader>
              <CardContent>
                <div className="space-y-4">
                  {teamMembers.map((member) => (
                    <div key={member.id} className="flex items-center justify-between p-4 rounded-lg bg-background border border-border">
                      <div className="flex items-center gap-3">
                        <Avatar>
                          <AvatarFallback className="bg-primary/10 text-primary">
                            {member.name.split(' ').map(n => n[0]).join('')}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium">{member.name}</p>
                          <p className="text-sm text-muted-foreground">{member.email}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-3">
                        <Badge variant={member.role === 'Admin' ? 'default' : 'secondary'}>
                          {member.role}
                        </Badge>
                        <Button variant="ghost" size="icon">
                          <Mail className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="billing">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Billing & Subscription</CardTitle>
                <CardDescription>Manage your subscription and billing information</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="p-6 rounded-lg bg-primary/10 border border-primary/20">
                  <div className="flex items-center justify-between">
                    <div>
                      <p className="text-sm text-muted-foreground">Current Plan</p>
                      <p className="text-2xl font-bold text-primary">Pro</p>
                    </div>
                    <Badge className="bg-primary text-primary-foreground">Active</Badge>
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-4 text-sm">
                    <div>
                      <p className="text-muted-foreground">Jobs</p>
                      <p className="font-medium">Unlimited</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">Team Members</p>
                      <p className="font-medium">Up to 10</p>
                    </div>
                    <div>
                      <p className="text-muted-foreground">AI Credits</p>
                      <p className="font-medium">5,000/month</p>
                    </div>
                  </div>
                </div>

                <div className="flex gap-3">
                  <Button variant="outline">View Invoice History</Button>
                  <Button>Manage Subscription</Button>
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          <TabsContent value="notifications">
            <Card className="bg-card border-border">
              <CardHeader>
                <CardTitle>Notification Preferences</CardTitle>
                <CardDescription>Choose what notifications you want to receive</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="flex items-center justify-between p-4 rounded-lg bg-background border border-border">
                  <div>
                    <p className="font-medium">Email on new application</p>
                    <p className="text-sm text-muted-foreground">
                      Receive an email when a candidate applies to your jobs
                    </p>
                  </div>
                  <Switch
                    checked={emailNotifications}
                    onCheckedChange={setEmailNotifications}
                  />
                </div>

                <div className="flex items-center justify-between p-4 rounded-lg bg-background border border-border">
                  <div>
                    <p className="font-medium">Email on interview completion</p>
                    <p className="text-sm text-muted-foreground">
                      Get notified when an interview is completed
                    </p>
                  </div>
                  <Switch
                    checked={interviewNotifications}
                    onCheckedChange={setInterviewNotifications}
                  />
                </div>

                <Button onClick={handleSave}>Save Preferences</Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </RecruiterLayout>
  );
}

