"use client";

import { AuditEventSchema } from "@localguard/contracts";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, Clock3, Fingerprint, Link2, ScrollText, UserRound } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/components/providers/auth-provider";
import { EmptyState, ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return "Unable to format this payload.";
  }
}

export function AuditEventScreen({ eventId }: { eventId: string }) {
  const { user } = useAuth();
  const canAudit = user?.role === "reviewer" || user?.role === "admin";
  const event = useQuery({
    queryKey: queryKeys.auditEvent(eventId),
    queryFn: () => apiRequest(`/audit-events/${encodeURIComponent(eventId)}`, AuditEventSchema),
    enabled: canAudit,
  });

  if (!canAudit) {
    return <InlineBanner title="Reviewer role required" tone="info">Audit records are restricted to reviewer and administrator accounts.</InlineBanner>;
  }
  if (event.isLoading) return <PageSkeleton />;
  if (event.isError) return <ErrorState error={event.error} onRetry={() => event.refetch()} />;
  if (!event.data) return null;

  const record = event.data;
  return (
    <div className="space-y-6">
      <Link className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-semibold text-muted-foreground hover:text-brand" href="/audit"><ArrowLeft aria-hidden className="size-4" />Back to audit log</Link>
      <PageHeader actions={<StatusBadge status={record.outcome} />} description={`${record.resource_type} event recorded ${formatDateTime(record.occurred_at)}`} eyebrow="Audit event" title={record.action} />

      <section aria-label="Event metadata" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="panel p-5"><Clock3 aria-hidden className="size-5 text-brand" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Recorded</p><p className="mt-1 font-semibold">{formatDateTime(record.occurred_at)}</p></div>
        <div className="panel p-5"><UserRound aria-hidden className="size-5 text-evidence" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Actor</p><p className="mt-1 break-all font-mono text-xs">{record.actor_id ?? "System"}</p></div>
        <div className="panel p-5"><Link2 aria-hidden className="size-5 text-pending" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Resource</p><p className="mt-1 font-semibold">{record.resource_type}</p><p className="mt-1 break-all font-mono text-xs text-muted-foreground">{record.resource_id ?? "—"}</p></div>
        <div className="panel p-5"><Fingerprint aria-hidden className="size-5 text-brand" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Correlation ID</p><p className="mt-1 break-all font-mono text-xs">{record.correlation_id}</p></div>
      </section>

      <section className="panel overflow-hidden">
        <header className="border-b border-border px-5 py-4 sm:px-6"><h2 className="font-heading text-lg font-semibold">Redacted detail</h2><p className="mt-1 text-sm text-muted-foreground">Sensitive keys are redacted by the API before this representation is returned.</p></header>
        <div className="p-5 sm:p-6">
          {Object.keys(record.detail).length ? <pre className="max-h-[32rem] overflow-auto rounded-lg bg-slate-950 p-4 text-xs leading-5 whitespace-pre-wrap text-slate-100">{safeJson(record.detail)}</pre> : <EmptyState description="This event does not expose any detail fields." icon={<ScrollText aria-hidden className="size-6" />} title="No detail recorded" />}
        </div>
      </section>

      <section className="panel p-5 sm:p-6">
        <h2 className="font-heading text-lg font-semibold">Causality</h2>
        <dl className="mt-4 grid gap-4 text-sm sm:grid-cols-2"><div><dt className="text-muted-foreground">Causation ID</dt><dd className="mt-1 break-all font-mono text-xs">{record.causation_id ?? "Not recorded"}</dd></div><div><dt className="text-muted-foreground">Workflow thread</dt><dd className="mt-1 break-all font-mono text-xs">{record.thread_id ?? "Not attached"}</dd></div></dl>
      </section>
    </div>
  );
}
