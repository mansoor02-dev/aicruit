'use client';

import Link from "next/link";
import { usePathname } from "next/navigation";
import { forwardRef, ComponentPropsWithoutRef } from "react";
import { cn } from "@/lib/utils";

interface NavLinkProps extends Omit<ComponentPropsWithoutRef<typeof Link>, "className"> {
  className?: string;
  activeClassName?: string;
  pendingClassName?: string;
  children: React.ReactNode;
}

const NavLink = forwardRef<HTMLAnchorElement, NavLinkProps>(
  ({ className, activeClassName, pendingClassName, href, children, ...props }, ref) => {
    const pathname = usePathname();
    const hrefStr = typeof href === "string" ? href : "";
    const isActive =
      pathname === hrefStr || (hrefStr !== "/" && hrefStr && pathname?.startsWith(hrefStr + "/"));

    return (
      <Link
        ref={ref}
        href={href}
        data-active={isActive ? "true" : undefined}
        className={cn(
          "transition-all duration-200 ease-smooth",
          className,
          isActive && activeClassName,
        )}
        {...props}
      >
        {children}
      </Link>
    );
  },
);

NavLink.displayName = "NavLink";

export { NavLink };