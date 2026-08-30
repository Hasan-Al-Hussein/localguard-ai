import Link from "next/link";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Button } from "./button";

export function OperationalLink({
  children,
  className,
  href,
  title,
}: {
  children: ReactNode;
  className?: string;
  href: string;
  title?: string;
}) {
  return (
    <Link
      className={cn(
        "relative inline-flex font-semibold text-brand underline-offset-4 before:absolute before:-inset-x-2 before:-inset-y-3 before:content-[''] hover:underline focus-visible:rounded-sm",
        className,
      )}
      href={href}
      title={title}
    >
      {children}
    </Link>
  );
}

export function MobileRecordCard({ children }: { children: ReactNode }) {
  return <article className="panel min-w-0 p-3">{children}</article>;
}

const noticeToneClasses = {
  info: "border-info/25 bg-info-soft/70 text-info",
  pending: "border-pending/30 bg-pending-soft/70 text-pending",
} as const;

export function OperationalNotice({
  children,
  icon,
  title,
  tone,
}: {
  children: ReactNode;
  icon: ReactNode;
  title: string;
  tone: keyof typeof noticeToneClasses;
}) {
  return (
    <div
      aria-label={title}
      className={cn(
        "flex items-start gap-3 rounded-lg border px-3.5 py-3 text-sm text-foreground",
        noticeToneClasses[tone],
      )}
      role="note"
    >
      <span aria-hidden className="mt-0.5 shrink-0">{icon}</span>
      <div className="min-w-0 sm:flex sm:items-baseline sm:gap-2">
        <p className="shrink-0 font-semibold text-current">{title}</p>
        <div className="mt-0.5 text-xs leading-5 text-muted-foreground sm:mt-0">{children}</div>
      </div>
    </div>
  );
}

export function OperationalPagination({
  ariaLabel,
  first,
  isFetching,
  last,
  noun,
  onNext,
  onPrevious,
  pageSize,
  startOffset,
  summary,
  total,
}: {
  ariaLabel: string;
  first: number;
  isFetching: boolean;
  last: number;
  noun: string;
  onNext: () => void;
  onPrevious: () => void;
  pageSize: number;
  startOffset: number;
  summary?: ReactNode;
  total: number;
}) {
  if (total <= pageSize) return null;

  return (
    <nav
      aria-label={ariaLabel}
      className="flex flex-col gap-3 border-t border-border pt-3 text-sm sm:flex-row sm:items-center sm:justify-between"
    >
      <p className="text-xs tabular-nums text-muted-foreground sm:text-sm">
        {summary ?? <>Showing {first}–{last} of {total} {noun}</>}
      </p>
      <div className="flex gap-2">
        <Button
          className="flex-1 sm:flex-none"
          disabled={startOffset === 0 || isFetching}
          onClick={onPrevious}
          variant="secondary"
        >
          Previous
        </Button>
        <Button
          className="flex-1 sm:flex-none"
          disabled={startOffset + pageSize >= total || isFetching}
          onClick={onNext}
          variant="secondary"
        >
          Next
        </Button>
      </div>
    </nav>
  );
}
