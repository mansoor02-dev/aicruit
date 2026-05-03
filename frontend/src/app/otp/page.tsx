'use client';

import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { InputOTP, InputOTPGroup, InputOTPSlot, InputOTPSeparator } from '@/components/ui/input-otp';
import { Spinner } from '@/components/ui/spinner';
import { useToast } from '@/hooks/use-toast';
import { ArrowRight, Mail, ShieldCheck } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

function OTPVerificationInner() {
  const [otp, setOtp] = useState('');
  const [loading, setLoading] = useState(false);
  const [resendLoading, setResendLoading] = useState(false);
  const router = useRouter();
  const searchParams = useSearchParams();
  const { toast } = useToast();

  const email = searchParams.get('email');

  useEffect(() => {
    if (!email) router.push('/');
  }, [email, router]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!otp || otp.length !== 6) {
      toast({ title: 'Error', description: 'Please enter the 6-digit code', variant: 'destructive' });
      return;
    }
    setLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/confirm-signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, otp }),
      });
      if (response.ok) {
        toast({ title: 'Success', description: 'Account verified! Redirecting...' });
        setTimeout(() => router.push('/'), 1500);
      } else {
        const error = await response.json();
        toast({ title: 'Error', description: error.detail || 'Verification failed', variant: 'destructive' });
      }
    } catch {
      toast({ title: 'Error', description: 'Network error. Please try again.', variant: 'destructive' });
    } finally {
      setLoading(false);
    }
  };

  const handleResendOTP = async () => {
    setResendLoading(true);
    try {
      const response = await fetch(`${API_BASE_URL}/auth/resend-otp`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email }),
      });
      if (response.ok) {
        toast({ title: 'Sent', description: 'A new code has been sent to your email.' });
      } else {
        const error = await response.json();
        toast({ title: 'Error', description: error.detail || 'Failed to resend code', variant: 'destructive' });
      }
    } catch {
      toast({ title: 'Error', description: 'Network error. Please try again.', variant: 'destructive' });
    } finally {
      setResendLoading(false);
    }
  };

  if (!email) return null;

  return (
    <div className="relative min-h-screen flex items-center justify-center p-4 overflow-hidden">
      <div className="pointer-events-none absolute -top-32 -left-32 w-[420px] h-[420px] rounded-full bg-primary/15 blur-3xl animate-float" />
      <div className="pointer-events-none absolute -bottom-32 -right-24 w-[460px] h-[460px] rounded-full bg-warning/15 blur-3xl animate-float" style={{ animationDelay: '1s' }} />
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-25 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />

      <div className="relative w-full max-w-md animate-fade-in-up">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-4">
            <div className="relative w-14 h-14 rounded-2xl bg-brand-gradient flex items-center justify-center shadow-glow animate-scale-in">
              <Mail className="w-7 h-7 text-primary-foreground" />
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-success rounded-full flex items-center justify-center ring-2 ring-background">
                <ShieldCheck className="w-3 h-3 text-success-foreground" />
              </span>
            </div>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-foreground">Verify your email</h1>
          <p className="text-muted-foreground mt-2 text-sm">
            We&apos;ve sent a 6-digit code to <span className="text-foreground font-medium">{email}</span>
          </p>
        </div>

        <Card className="border-border/70 shadow-xl bg-card/95 animate-scale-in">
          <CardHeader className="space-y-1 pb-4">
            <CardTitle className="text-2xl text-center">Enter the code</CardTitle>
            <CardDescription className="text-center">
              Check your inbox for the verification code
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit} className="space-y-6">
              <div className="flex justify-center">
                <InputOTP maxLength={6} value={otp} onChange={(v) => setOtp(v.replace(/\D/g, ''))}>
                  <InputOTPGroup>
                    <InputOTPSlot index={0} />
                    <InputOTPSlot index={1} />
                    <InputOTPSlot index={2} />
                  </InputOTPGroup>
                  <InputOTPSeparator />
                  <InputOTPGroup>
                    <InputOTPSlot index={3} />
                    <InputOTPSlot index={4} />
                    <InputOTPSlot index={5} />
                  </InputOTPGroup>
                </InputOTP>
              </div>

              <Button type="submit" size="lg" className="w-full" disabled={loading || otp.length !== 6}>
                {loading ? (
                  <>
                    <Spinner size="sm" className="!border-primary-foreground/30 !border-t-primary-foreground" />
                    <span>Verifying...</span>
                  </>
                ) : (
                  <>
                    Verify account
                    <ArrowRight className="w-4 h-4" />
                  </>
                )}
              </Button>
            </form>

            <div className="mt-6 pt-6 border-t border-border text-center">
              <p className="text-sm text-muted-foreground mb-3">Didn&apos;t receive the code?</p>
              <Button variant="outline" onClick={handleResendOTP} disabled={resendLoading} className="w-full">
                {resendLoading ? <Spinner size="sm" /> : 'Resend code'}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

export default function OTPVerificationPage() {
  return (
    <Suspense fallback={<div className="min-h-screen flex items-center justify-center"><div className="spinner spinner-lg" /></div>}>
      <OTPVerificationInner />
    </Suspense>
  );
}