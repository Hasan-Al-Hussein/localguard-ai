import { CircleAlert, FileSearch, RefreshCw } from "lucide-react";
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
    <section className="panel relative flex min-h-64 flex-col items-center justify-center overflow-hidden p-8 text-center">
      <div aria-hidden className="absolute -top-24 left-1/2 size-64 -translate-x-1/2 rounded-full bg-evidence-soft/50 blur-3xl" />
      <span className="relative grid size-12 place-items-center rounded-2xl bg-surface-raised text-muted-foreground shadow-sm">
        {icon ?? <FileSearch aria-hidden className="size-6" />}
      </span>
      <h2 className="relative mt-4 font-heading text-lg font-bold">{title}</h2>
      <p className="relative mt-2 max-w-md text-sm text-muted-foreground">{description}</p>
      {action ? <div className="relative mt-5">{action}</div> : null}
    </section>
  );
}

export function PageSkeleton() {
  return (
    <div aria-label="Loading content" className="space-y-6" role="status">
      <div className="skeleton h-8 w-56 rounded-md" />
      <div className="skeleton h-4 w-full max-w-xl rounded" />
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <div className="skeleton h-40 rounded-xl" key={index} />
        ))}
      </div>
      <div className="skeleton h-80 rounded-xl" />
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

  return (
    <div className={`rounded-xl border p-4 text-sm text-foreground shadow-[inset_0_1px_0_rgb(255_255_255/0.55)] ${toneClasses[tone]}`}>
      <p className="font-semibold">{title}</p>
      <div className="mt-1 text-muted-foreground">{children}</div>
    </div>
  );
}
