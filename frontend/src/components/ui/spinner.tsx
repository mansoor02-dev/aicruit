import { cn } from "@/lib/utils";

interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  size?: "sm" | "md" | "lg";
}

export function Spinner({ size = "md", className, ...props }: SpinnerProps) {
  return (
    <div
      role="status"
      aria-label="Loading"
      className={cn(
        "spinner",
        size === "sm" && "spinner-sm",
        size === "lg" && "spinner-lg",
        className,
      )}
      {...props}
    />
  );
}

export function DotPulse({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div role="status" aria-label="Loading" className={cn("dot-pulse", className)} {...props}>
      <span /><span /><span />
    </div>
  );
}