import { ReactNode } from 'react';
import { Card, CardContent } from '@/components/ui/card';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatsCardProps {
  title: string;
  value: string | number;
  trend?: number;
  trendLabel?: string;
  icon?: ReactNode;
}

export const StatsCard = ({ title, value, trend, trendLabel, icon }: StatsCardProps) => {
  const isPositive = trend !== undefined && trend > 0;
  const isNegative = trend !== undefined && trend < 0;

  return (
    <Card className="card-hover relative overflow-hidden bg-card border-border group">
      <span className="pointer-events-none absolute inset-x-0 -top-px h-px bg-gradient-to-r from-transparent via-primary/40 to-transparent opacity-0 transition-opacity duration-500 group-hover:opacity-100" />
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-3xl font-bold tracking-tight text-foreground">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{trendLabel || 'vs last period'}</span>
              {trend !== undefined && (
                <span
                  className={cn(
                    'inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-xs font-semibold',
                    isPositive && 'bg-success/12 text-success',
                    isNegative && 'bg-destructive/10 text-destructive',
                  )}
                >
                  {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {Math.abs(trend)}%
                </span>
              )}
            </div>
          </div>
          {icon && (
            <div className="p-2.5 rounded-xl bg-accent text-accent-foreground transition-transform duration-300 ease-smooth group-hover:scale-110 group-hover:rotate-3">
              {icon}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-4 uppercase tracking-wider font-semibold">{title}</p>
      </CardContent>
    </Card>
  );
};