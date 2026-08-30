"use client";

import { AuditEventsResponseSchema, type AuditEvent } from "@localguard/contracts";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ScrollText } from "lucide-react";
import { useMemo, useState } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { EmptyState, ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { DataTable } from "@/components/ui/data-table";
import {
  MobileRecordCard,
  OperationalLink,
  OperationalNotice,
  OperationalPagination,
} from "@/components/ui/operational-list";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 15;

export function AuditScreen({ threadId }: { threadId?: string }) {
  const [offset, setOffset] = useState(0);
  const { user } = useAuth();
  const canAudit = user?.role === "reviewer" || user?.role === "admin";
  const requestOffset = threadId ? 0 : offset;
  const requestLimit = threadId ? 100 : PAGE_SIZE;
  const parameters = new URLSearchParams({
    offset: String(requestOffset),
    limit: String(requestLimit),
  });
  const filters = parameters.toString();
  const events = useQuery({
    queryKey: queryKeys.audit(filters),
    queryFn: () => apiRequest(`/audit-events?${filters}`, AuditEventsResponseSchema),
    enabled: canAudit,
    placeholderData: keepPreviousData,
  });

  const columns = useMemo<Array<ColumnDef<AuditEvent>>>(() => [
    { accessorKey: "occurred_at", header: "Time", cell: ({ row }) => <time className="whitespace-nowrap" dateTime={row.original.occurred_at}>{formatDateTime(row.original.occurred_at)}</time> },
    {
      accessorKey: "action",
      header: "Action",
      cell: ({ row }) => <OperationalLink href={`/audit/${encodeURIComponent(row.original.id)}`}>{row.original.action}</OperationalLink>,
    },
    { accessorKey: "resource_type", header: "Resource", cell: ({ row }) => <span>{row.original.resource_type}<span className="block max-w-40 truncate font-mono text-xs text-muted-foreground" title={row.original.resource_id ?? undefined}>{row.original.resource_id ?? "—"}</span></span> },
    { accessorKey: "outcome", header: "Outcome", cell: ({ row }) => <StatusBadge status={row.original.outcome} /> },
    { accessorKey: "actor_id", header: "Actor", cell: ({ row }) => row.original.actor_id ? <span className="block max-w-36 truncate font-mono text-xs" title={row.original.actor_id}>{row.original.actor_id}</span> : "System" },
    { accessorKey: "correlation_id", header: "Correlation", cell: ({ row }) => <span className="block max-w-36 truncate font-mono text-xs" title={row.original.correlation_id}>{row.original.correlation_id}</span> },
  ], []);

  if (!canAudit) {
    return (
      <div className="space-y-5">
        <PageHeader description="Inspect redacted, append-only records for local workflow activity." eyebrow="Accountability" title="Audit log" />
        <InlineBanner title="Reviewer role required" tone="info">Audit records are restricted to reviewer and administrator accounts.</InlineBanner>
      </div>
    );
  }
  if (events.isLoading) return <PageSkeleton />;
  if (events.isError) return <ErrorState error={events.error} onRetry={() => events.refetch()} />;

  const rows = threadId
    ? (events.data?.items ?? [])
        .filter((event) => event.thread_id === threadId)
        .toSorted((left, right) => (
          new Date(left.occurred_at).getTime() - new Date(right.occurred_at).getTime()
        ))
    : events.data?.items ?? [];
  const total = threadId ? rows.length : events.data?.total ?? 0;
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + rows.length, total);
  return (
    <div className="space-y-5">
      <PageHeader
        description={threadId
          ? "Follow the ordered request, analysis, proposal, decision, resume, and task records for one workflow."
          : "Follow redacted, append-only records returned by the authoritative local audit API."}
        eyebrow="Accountability"
        title={threadId ? "Workflow audit chain" : "Audit log"}
      />
      {threadId ? (
        <OperationalNotice icon={<ScrollText className="size-4" />} title="One workflow thread" tone="info">
          <span className="break-all font-mono text-xs">{threadId}</span>
        </OperationalNotice>
      ) : null}
      <div className={events.isPlaceholderData ? "opacity-60" : undefined}>
        <DataTable
          columns={columns}
          data={rows}
          empty={<EmptyState description={threadId ? "No audit records were returned for this workflow thread." : "No audit records have been returned for this workspace."} icon={<ScrollText aria-hidden className="size-6" />} title="No audit events yet" />}
          getRowId={(event) => event.id}
          wide
          mobileRow={(event) => (
            <MobileRecordCard>
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <OperationalLink className="max-w-full whitespace-normal text-left" href={`/audit/${encodeURIComponent(event.id)}`} title={event.action}><span className="line-clamp-2">{event.action}</span></OperationalLink>
                  <p className="mt-1 truncate text-xs text-muted-foreground" title={event.resource_id ?? undefined}>
                    {event.resource_type}{event.resource_id ? ` · ${event.resource_id}` : ""}
                  </p>
                </div>
                <StatusBadge status={event.outcome} />
              </div>
              <div className="mt-2 flex items-center justify-between gap-3 border-t border-border/80 pt-2 text-xs text-muted-foreground">
                <time className="shrink-0" dateTime={event.occurred_at}>{formatDateTime(event.occurred_at)}</time>
                <span className="min-w-0 truncate font-mono" title={event.correlation_id}>{event.correlation_id}</span>
              </div>
            </MobileRecordCard>
          )}
        />
      </div>
      {!threadId ? (
        <OperationalPagination
          ariaLabel="Audit pagination"
          first={first}
          isFetching={events.isFetching}
          last={last}
          noun="events"
          onNext={() => setOffset((value) => value + PAGE_SIZE)}
          onPrevious={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
          pageSize={PAGE_SIZE}
          startOffset={offset}
          total={total}
        />
      ) : null}
    </div>
  );
}
