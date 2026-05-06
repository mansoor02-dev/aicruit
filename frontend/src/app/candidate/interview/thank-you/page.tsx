'use client';

import { Suspense } from 'react';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { CheckCircle2, Briefcase, ListChecks } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';

function ThankYouContent() {
  const searchParams = useSearchParams();
  const applicationId = searchParams.get('applicationId');

  const primaryHref = applicationId
    ? `/candidate/applications/${applicationId}`
    : '/candidate/applications';

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-10">
      <Card className="w-full max-w-lg bg-card border-border shadow-xl animate-fade-in-up">
        <CardContent className="p-8 sm:p-10 text-center space-y-6">
          <div className="relative mx-auto w-24 h-24">
            <div className="absolute inset-0 rounded-full bg-success/15 animate-pulse" />
            <div className="relative w-24 h-24 rounded-full bg-success flex items-center justify-center shadow-lg">
              <CheckCircle2 className="w-12 h-12 text-success-foreground" />
            </div>
          </div>

          <div className="space-y-3">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-foreground">
              Thanks for completing your interview
            </h1>
            <p className="text-muted-foreground">
              We&apos;ll review your responses and get back to you soon. You can track the status under My Applications.
            </p>
          </div>

          <div className="flex flex-col sm:flex-row gap-3 pt-2">
            <Button asChild size="lg" className="flex-1 gap-2">
              <Link href={primaryHref}>
                <ListChecks className="w-4 h-4" />
                View My Applications
              </Link>
            </Button>
            <Button asChild size="lg" variant="outline" className="flex-1 gap-2">
              <Link href="/candidate/job">
                <Briefcase className="w-4 h-4" />
                Back to Jobs
              </Link>
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default function InterviewThankYouPage() {
  return (
    <Suspense fallback={null}>
      <ThankYouContent />
    </Suspense>
  );
}
