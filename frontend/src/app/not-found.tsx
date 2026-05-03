'use client';

import Link from 'next/link';
import { Button } from '@/components/ui/button';
import { Home, ArrowLeft } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background">
      <div className="pointer-events-none absolute -top-32 -left-32 w-[420px] h-[420px] rounded-full bg-primary/15 blur-3xl animate-float" />
      <div className="pointer-events-none absolute -bottom-40 -right-32 w-[460px] h-[460px] rounded-full bg-warning/15 blur-3xl animate-float" style={{ animationDelay: '1s' }} />
      <div className="pointer-events-none absolute inset-0 bg-grid opacity-25 [mask-image:radial-gradient(ellipse_at_center,black_30%,transparent_75%)]" />

      <div className="relative text-center px-6 animate-fade-in-up">
        <p className="text-[8rem] sm:text-[10rem] leading-none font-extrabold text-brand-gradient drop-shadow-sm select-none">
          404
        </p>
        <h1 className="mt-2 text-2xl sm:text-3xl font-bold text-foreground">Page not found</h1>
        <p className="mt-2 text-muted-foreground max-w-md mx-auto">
          The page you&apos;re looking for has moved or no longer exists.
        </p>

        <div className="mt-8 flex items-center justify-center gap-3">
          <Button asChild size="lg">
            <Link href="/">
              <Home className="w-4 h-4" />
              Return home
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg">
            <Link href="javascript:history.back()" onClick={(e) => { e.preventDefault(); if (typeof history !== 'undefined') history.back(); }}>
              <ArrowLeft className="w-4 h-4" />
              Go back
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
}