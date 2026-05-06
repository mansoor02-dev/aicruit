import { cn } from "@/lib/utils";
import { Spinner } from "@/components/ui/spinner";

interface PageLoaderProps {
  label?: string;
  fullscreen?: boolean;
  className?: string;
}

export function PageLoader({ label = "Loading...", fullscreen = false, className }: PageLoaderProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 animate-fade-in",
        fullscreen ? "min-h-[60vh]" : "py-16",
        className,
      )}
    >
      <div className="relative">
        <div className="absolute inset-0 -m-3 rounded-full bg-primary/15 blur-xl animate-glow-pulse" />
        <Spinner size="lg" className="relative" />
      </div>
      {label && (
        <p className="text-sm text-muted-foreground font-medium tracking-wide">{label}</p>
      )}
    </div>
  );
}

interface CardSkeletonProps {
  rows?: number;
  className?: string;
}

export function CardSkeleton({ rows = 3, className }: CardSkeletonProps) {
  return (
    <div className={cn("rounded-xl border border-border bg-card p-6 space-y-3 animate-fade-in", className)}>
      <div className="shimmer h-5 w-2/5 rounded-md" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="shimmer h-4 rounded-md" style={{ width: `${90 - i * 12}%` }} />
      ))}
    </div>
  );
}