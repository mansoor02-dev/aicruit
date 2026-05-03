'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { NavLink } from '@/components/NavLink';
import { useAuth } from '@/contexts/AuthContext';
import {
  Briefcase,
  FileText,
  User,
  LogOut,
  Bell,
  Search,
  ChevronDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';

interface CandidateLayoutProps {
  children: ReactNode;
}

const navItems = [
  { title: 'Browse Jobs', url: '/candidate/job', icon: Briefcase },
  { title: 'My Applications', url: '/candidate/applications', icon: FileText },
  { title: 'Profile', url: '/candidate/profile', icon: User },
];

export const CandidateLayout = ({ children }: CandidateLayoutProps) => {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="h-16 glass border-b border-border sticky top-0 z-50 animate-fade-in-down">
        <div className="container h-full flex items-center justify-between">
          <div className="flex items-center gap-8">
            <Link href="/candidate/job" className="flex items-center gap-2.5 group">
              <div className="w-9 h-9 rounded-xl bg-brand-gradient flex items-center justify-center shadow-sm transition-transform duration-300 ease-smooth group-hover:scale-105 group-hover:shadow-glow">
                <span className="text-primary-foreground font-bold text-sm">AI</span>
              </div>
              <span className="text-xl font-bold tracking-tight text-foreground">AIcruit</span>
            </Link>

            <nav className="hidden md:flex items-center gap-1">
              {navItems.map((item, idx) => (
                <NavLink
                  key={item.title}
                  href={item.url}
                  style={{ animationDelay: `${idx * 50}ms` } as React.CSSProperties}
                  className="group relative flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  activeClassName="bg-accent text-accent-foreground"
                >
                  <item.icon className="w-4 h-4 transition-transform duration-200 ease-smooth group-hover:scale-110 group-data-[active=true]:text-primary" />
                  <span>{item.title}</span>
                </NavLink>
              ))}
            </nav>
          </div>

          <div className="flex items-center gap-3">
            <div className="relative hidden md:block w-64">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input placeholder="Search jobs..." className="pl-10 bg-card/60" />
            </div>

            <Button variant="ghost" size="icon" className="relative">
              <Bell className="w-5 h-5" />
              <span className="absolute top-2 right-2 w-2 h-2 bg-primary rounded-full ring-2 ring-card animate-glow-pulse" />
            </Button>

            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="flex items-center gap-2 pl-2 pr-2.5">
                  <Avatar className="w-8 h-8 ring-2 ring-primary/15">
                    <AvatarFallback className="bg-brand-gradient text-primary-foreground font-semibold">
                      {user?.name?.charAt(0).toUpperCase() || 'U'}
                    </AvatarFallback>
                  </Avatar>
                  <span className="hidden md:inline font-medium text-sm">{user?.name || 'User'}</span>
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem asChild>
                  <Link href="/candidate/profile">Profile</Link>
                </DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                  <LogOut className="w-4 h-4 mr-2" />
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </header>

      <main className="container py-8 animate-fade-in-up">
        {children}
      </main>
    </div>
  );
};