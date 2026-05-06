'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth, UserRole } from '@/contexts/AuthContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Tabs, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Spinner } from '@/components/ui/spinner';
import { useToast } from '@/hooks/use-toast';
import { Briefcase, User, ArrowRight, Sparkles } from 'lucide-react';

type AuthMode = 'login' | 'signup';

const Auth = () => {
  const [mode, setMode] = useState<AuthMode>('login');
  const [role, setRole] = useState<UserRole>('RECRUITER');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, signup } = useAuth();
  const router = useRouter();
  const { toast } = useToast();

  const validatePassword = (pwd: string) => {
    const hasUpper = /[A-Z]/.test(pwd);
    const hasLower = /[a-z]/.test(pwd);
    const hasNumber = /[0-9]/.test(pwd);
    const hasSymbol = /[!@#$%^&*()_+\-=\[\]{};':"\\|,.<>\/?]/.test(pwd);
    const hasLength = pwd.length >= 8;
    return hasUpper && hasLower && hasNumber && hasSymbol && hasLength;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();

    if (!email || !password) {
      toast({ title: 'Error', description: 'Please fill in all required fields', variant: 'destructive' });
      return;
    }
    if (!validatePassword(password)) {
      toast({
        title: 'Invalid Password',
        description: 'Password must be at least 8 characters with uppercase, lowercase, number, and symbol',
        variant: 'destructive',
      });
      return;
    }
    if (mode === 'signup' && !name) {
      toast({ title: 'Error', description: 'Please enter your full name', variant: 'destructive' });
      return;
    }
    if (mode === 'signup' && role === 'RECRUITER' && (!phone || !companyName)) {
      toast({ title: 'Error', description: 'Please enter your phone number and company name', variant: 'destructive' });
      return;
    }
    if (mode === 'signup' && role === 'CANDIDATE' && !phone) {
      toast({ title: 'Error', description: 'Please enter your phone number', variant: 'destructive' });
      return;
    }

    setLoading(true);
    try {
      if (mode === 'login') {
        await login(email, password, role);
        toast({ title: 'Success', description: 'Welcome back!' });
        if (role === 'RECRUITER') router.push('/recruiter/dashboard');
        else router.push('/candidate/job');
        return;
      }
      await signup(email, password, name, role, phone, companyName);
      toast({
        title: 'Verify your email',
        description: 'We have sent you a 6-digit OTP. Please verify to continue.',
      });
      router.push(`/otp?email=${encodeURIComponent(email)}&role=${role}`);
    } catch (error: any) {
      toast({
        title: 'Error',
        description: error?.message || 'Authentication failed. Please try again.',
        variant: 'destructive',
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 overflow-hidden">
      {/* Decorative blobs */}
      <div className="pointer-events-none absolute -top-32 -left-32 w-[420px] h-[420px] rounded-full bg-primary/15 blur-3xl animate-float" />
      <div className="pointer-events-none absolute -bottom-32 -right-24 w-[460px] h-[460px] rounded-full bg-warning/15 blur-3xl animate-float" style={{ animationDelay: '1s' }} />
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-30 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />

      <div className="relative w-full max-w-md animate-fade-in-up">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-5">
            <div className="w-14 h-14 rounded-2xl bg-brand-gradient flex items-center justify-center shadow-glow animate-scale-in">
              <span className="text-primary-foreground font-bold text-xl">AI</span>
            </div>
          </div>
          <h1 className="text-4xl font-extrabold tracking-tight">
            <span className="text-brand-gradient">AIcruit</span>
          </h1>
          <p className="text-muted-foreground mt-2 inline-flex items-center gap-1.5 text-sm">
            <Sparkles className="w-3.5 h-3.5 text-primary" />
            AI-Powered Recruitment Platform
          </p>
        </div>

        <Card className="border-border/70 shadow-xl backdrop-blur-sm bg-card/95 animate-scale-in">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-2xl text-center">
              {mode === 'login' ? 'Welcome back' : 'Create your account'}
            </CardTitle>
            <CardDescription className="text-center">
              {mode === 'login' ? 'Sign in to continue to your dashboard' : 'Get started with AIcruit in seconds'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Tabs
              value={role || 'RECRUITER'}
              onValueChange={(v) => {
                setRole(v as UserRole);
                if (v === 'CANDIDATE') setCompanyName('');
              }}
              className="mb-6"
            >
              <TabsList className="grid w-full grid-cols-2 bg-muted p-1 h-11">
                <TabsTrigger
                  value="RECRUITER"
                  className="flex items-center gap-2 rounded-md transition-all data-[state=active]:bg-card data-[state=active]:text-primary data-[state=active]:shadow-sm"
                >
                  <Briefcase className="w-4 h-4" />
                  Recruiter
                </TabsTrigger>
                <TabsTrigger
                  value="CANDIDATE"
                  className="flex items-center gap-2 rounded-md transition-all data-[state=active]:bg-card data-[state=active]:text-primary data-[state=active]:shadow-sm"
                >
                  <User className="w-4 h-4" />
                  Candidate
                </TabsTrigger>
              </TabsList>
            </Tabs>

            <form onSubmit={handleSubmit} className="space-y-4">
              {mode === 'signup' && (
                <div className="space-y-2 animate-fade-in-up">
                  <Label htmlFor="name">Full Name</Label>
                  <Input id="name" placeholder="John Doe" value={name} onChange={(e) => setName(e.target.value)} />
                </div>
              )}

              <div className="space-y-2 animate-fade-in-up" style={{ animationDelay: '50ms' }}>
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="you@example.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </div>

              <div className="space-y-2 animate-fade-in-up" style={{ animationDelay: '100ms' }}>
                <Label htmlFor="password">Password</Label>
                <Input
                  id="password"
                  type="password"
                  placeholder="••••••••"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                {mode === 'signup' && (
                  <p className="text-xs text-muted-foreground">
                    Min 8 characters with uppercase, lowercase, number, and symbol
                  </p>
                )}
              </div>

              {mode === 'signup' && (
                <>
                  <div className="space-y-2 animate-fade-in-up" style={{ animationDelay: '150ms' }}>
                    <Label htmlFor="phone">Phone Number</Label>
                    <Input
                      id="phone"
                      placeholder="+1 (555) 123-4567"
                      value={phone}
                      onChange={(e) => setPhone(e.target.value)}
                    />
                  </div>
                  {role === 'RECRUITER' && (
                    <div className="space-y-2 animate-fade-in-up" style={{ animationDelay: '200ms' }}>
                      <Label htmlFor="companyName">Company Name</Label>
                      <Input
                        id="companyName"
                        placeholder="Your Company"
                        value={companyName}
                        onChange={(e) => setCompanyName(e.target.value)}
                      />
                    </div>
                  )}
                </>
              )}

              <Button type="submit" size="lg" className="w-full mt-2" disabled={loading}>
                {loading ? (
                  <>
                    <Spinner size="sm" className="!border-primary-foreground/30 !border-t-primary-foreground" />
                    <span>Please wait...</span>
                  </>
                ) : (
                  <>
                    {mode === 'login' ? 'Sign In' : 'Create Account'}
                    <ArrowRight className="w-4 h-4 transition-transform group-hover:translate-x-0.5" />
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 text-center">
              <button
                type="button"
                onClick={() => setMode(mode === 'login' ? 'signup' : 'login')}
                className="text-sm text-muted-foreground hover:text-primary transition-colors"
              >
                {mode === 'login' ? (
                  <>
                    Don&apos;t have an account?{' '}
                    <span className="font-semibold text-primary hover:underline">Sign up</span>
                  </>
                ) : (
                  <>
                    Already have an account?{' '}
                    <span className="font-semibold text-primary hover:underline">Sign in</span>
                  </>
                )}
              </button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default Auth;