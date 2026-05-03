'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/contexts/AuthContext';
import Auth from '@/components/Auth';
import { PageLoader } from '@/components/ui/page-loader';

export default function HomePage() {
  const { isAuthenticated, user } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (isAuthenticated) {
      if (user?.role === 'RECRUITER') router.push('/recruiter/dashboard');
      else if (user?.role === 'CANDIDATE') router.push('/candidate/job');
    }
  }, [isAuthenticated, user, router]);

  if (isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <PageLoader fullscreen label="Redirecting to your dashboard..." />
      </div>
    );
  }

  return <Auth />;
}