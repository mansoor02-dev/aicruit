'use client';

import { ReactNode } from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { NavLink } from '@/components/NavLink';
import { useAuth } from '@/contexts/AuthContext';
import {
  LayoutDashboard,
  Briefcase,
  Users,
  Settings,
  LogOut,
  Bell,
  Search,
  ChevronDown,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';

interface RecruiterLayoutProps {
  children: ReactNode;
}

const navItems = [
  { title: 'Overview', url: '/recruiter/dashboard', icon: LayoutDashboard },
  { title: 'Jobs', url: '/recruiter/job', icon: Briefcase },
  { title: 'Candidates', url: '/recruiter/candidates', icon: Users },
  { title: 'Settings', url: '/recruiter/settings', icon: Settings },
];

export const RecruiterLayout = ({ children }: RecruiterLayoutProps) => {
  const { user, logout } = useAuth();
  const router = useRouter();

  const handleLogout = () => {
    logout();
    router.push('/');
  };

  return (
    <div className="min-h-screen bg-background flex">
      {/* Sidebar */}
      <aside className="w-64 bg-sidebar/80 glass border-r border-sidebar-border flex flex-col sticky top-0 h-screen animate-slide-in-left">
        <div className="p-6 border-b border-sidebar-border">
          <Link href="/recruiter/dashboard" className="flex items-center gap-2.5 group">
            <div className="w-9 h-9 rounded-xl bg-brand-gradient flex items-center justify-center shadow-sm transition-transform duration-300 ease-smooth group-hover:scale-105 group-hover:shadow-glow">
              <span className="text-primary-foreground font-bold text-sm">AI</span>
            </div>
            <span className="text-xl font-bold tracking-tight text-foreground">AIcruit</span>
          </Link>
        </div>

        <nav className="flex-1 p-4">
          <ul className="space-y-1">
            {navItems.map((item, idx) => (
              <li key={item.title} style={{ animationDelay: `${idx * 50}ms` }} className="animate-fade-in-up">
                <NavLink
                  href={item.url}
                  className="group relative flex items-center gap-3 px-3.5 py-2.5 rounded-lg text-sm font-medium text-muted-foreground hover:bg-accent hover:text-accent-foreground"
                  activeClassName="bg-accent text-accent-foreground shadow-xs"
                >
                  <item.icon className="w-[18px] h-[18px] transition-transform duration-200 ease-smooth group-hover:scale-110 group-data-[active=true]:text-primary" />
                  <span>{item.title}</span>
                  <span className="absolute left-0 top-1/2 -translate-y-1/2 h-5 w-1 rounded-r-full bg-primary opacity-0 transition-opacity duration-200 group-data-[active=true]:opacity-100" />
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>

        <div className="p-4 border-t border-sidebar-border">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-muted-foreground hover:text-destructive hover:bg-destructive/10"
            onClick={handleLogout}
          >
            <LogOut className="w-[18px] h-[18px]" />
            <span>Logout</span>
          </Button>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 flex flex-col min-w-0">
        <header className="h-16 glass border-b border-border flex items-center justify-between px-6 sticky top-0 z-30 animate-fade-in-down">
          <div className="flex items-center gap-4 flex-1 max-w-md">
            <div className="relative flex-1">
              <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input placeholder="Search..." className="pl-10 bg-card/60" />
            </div>
          </div>

          <div className="flex items-center gap-3">
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
                  <span className="font-medium text-sm">{user?.name || 'User'}</span>
                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuItem>Profile</DropdownMenuItem>
                <DropdownMenuItem>Settings</DropdownMenuItem>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="text-destructive focus:text-destructive">
                  Logout
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6 animate-fade-in-up">
          {children}
        </main>
      </div>
    </div>
  );
};