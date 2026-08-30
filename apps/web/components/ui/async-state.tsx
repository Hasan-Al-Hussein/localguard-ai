import { BadgeCheck, CircleAlert, FileSearch, Info, RefreshCw, ShieldAlert, TriangleAlert } from "lucide-react";
import type { ReactNode } from "react";
import { ApiError } from "@/lib/api-client";
import { Button } from "./button";

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const apiError = error instanceof ApiError ? error : null;
  return (
    <section className="panel mx-auto max-w-2xl p-6" role="alert">
      <div className="flex items-start gap-4">
        <span className="grid size-10 shrink-0 place-items-center rounded-lg bg-danger-soft text-danger">
          <CircleAlert aria-hidden className="size-5" />
        </span>
        <div>
          <h2 className="font-heading text-lg font-semibold">We could not load this view</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "The local service returned an unexpected response."}
          </p>
          {apiError?.correlationId ? (
            <p className="mt-2 font-mono text-xs text-muted-foreground">Correlation ID: {apiError.correlationId}</p>
          ) : null}
          {onRetry ? (
            <Button className="mt-4" icon={<RefreshCw aria-hidden className="size-4" />} onClick={onRetry} variant="secondary">
              Try again
            </Button>
          ) : null}
        </div>
      </div>
    </section>
  );
}

export function EmptyState({
  title,
  description,
  action,
  icon,
}: {
  title: string;
  description: string;
  action?: ReactNode;
  icon?: ReactNode;
}) {
  return (
    <section className="panel relative flex min-h-44 flex-col items-center justify-center overflow-hidden p-6 text-center sm:p-7">
      <div aria-hidden className="absolute -top-20 left-1/2 size-48 -translate-x-1/2 rounded-full bg-evidence-soft/35 blur-3xl" />
      <span className="relative grid size-10 place-items-center rounded-xl border border-border bg-surface-raised text-muted-foreground">
        {icon ?? <FileSearch aria-hidden className="size-6" />}
      </span>
      <h2 className="relative mt-3 font-heading text-base font-bold sm:text-lg">{title}</h2>
      <p className="relative mt-1.5 max-w-md text-sm text-muted-foreground">{description}</p>
      {action ? <div className="relative mt-4">{action}</div> : null}
    </section>
  );
}

export function PageSkeleton() {
  return (
    <div aria-label="Loading content" className="space-y-4" role="status">
      <div className="skeleton h-8 w-56 rounded-md" />
      <div className="skeleton h-4 w-full max-w-xl rounded" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton h-28 rounded-xl" key={index} />
        ))}
      </div>
      <div className="space-y-2 rounded-xl border border-border bg-surface p-4">
        {Array.from({ length: 5 }, (_, index) => <div className="skeleton h-10 rounded-lg" key={index} />)}
      </div>
      <span className="sr-only">Loading</span>
    </div>
  );
}

export function InlineBanner({ tone, title, children }: { tone: "info" | "pending" | "danger" | "evidence"; title: string; children: ReactNode }) {
  const toneClasses = {
    info: "border-info/25 bg-info-soft text-info",
    pending: "border-pending/25 bg-pending-soft text-pending",
    danger: "border-danger/25 bg-danger-soft text-danger",
    evidence: "border-evidence/25 bg-evidence-soft text-evidence",
  } as const;
  const icons = {
    info: Info,
    pending: ShieldAlert,
    danger: TriangleAlert,
    evidence: BadgeCheck,
  } as const;
  const Icon = icons[tone];

  return (
    <div className={`flex items-start gap-3 rounded-xl border px-4 py-3 text-sm text-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.55)] ${toneClasses[tone]}`}>
      <span className="mt-0.5 grid size-7 shrink-0 place-items-center rounded-lg bg-white/55"><Icon aria-hidden className="size-4" /></span>
      <div className="min-w-0"><p className="font-semibold">{title}</p><div className="mt-0.5 text-muted-foreground">{children}</div></div>
    </div>
  );
}
