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
  const isPositive = trend && trend > 0;
  const isNegative = trend && trend < 0;

  return (
    <Card className="bg-card border-border hover:shadow-lg transition-shadow">
      <CardContent className="p-6">
        <div className="flex items-start justify-between">
          <div className="space-y-2">
            <p className="text-3xl font-bold text-foreground">
              {typeof value === 'number' ? value.toLocaleString() : value}
            </p>
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">{trendLabel || 'vs last period'}</span>
              {trend !== undefined && (
                <span className={cn(
                  "flex items-center gap-1 text-sm font-medium",
                  isPositive && "text-green-500",
                  isNegative && "text-destructive"
                )}>
                  {isPositive ? <TrendingUp className="w-3 h-3" /> : <TrendingDown className="w-3 h-3" />}
                  {Math.abs(trend)}%
                </span>
              )}
            </div>
          </div>
          {icon && (
            <div className="p-2 bg-accent rounded-lg">
              {icon}
            </div>
          )}
        </div>
        <p className="text-xs text-muted-foreground mt-3 uppercase tracking-wide font-medium">{title}</p>
      </CardContent>
    </Card>
  );
};
