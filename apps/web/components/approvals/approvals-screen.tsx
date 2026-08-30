"use client";

import { ProposalsResponseSchema, type Proposal } from "@localguard/contracts";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ClipboardCheck } from "lucide-react";
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
import { formatDate, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 15;

export function ApprovalsScreen() {
  const [offset, setOffset] = useState(0);
  const { user } = useAuth();
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  const parameters = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) });
  const filters = parameters.toString();
  const approvals = useQuery({
    queryKey: queryKeys.approvals(filters),
    queryFn: () => apiRequest(`/approvals?${filters}`, ProposalsResponseSchema),
    enabled: canReview,
    placeholderData: keepPreviousData,
    refetchInterval: (query) => query.state.data?.items.some((proposal) => proposal.state === "pending") ? 10_000 : false,
  });

  const columns = useMemo<Array<ColumnDef<Proposal>>>(() => [
    {
      accessorKey: "title",
      header: "Proposal",
      cell: ({ row }) => (
        <div className="max-w-sm">
          <OperationalLink href={`/approvals/${encodeURIComponent(row.original.id)}`}>{row.original.title}</OperationalLink>
          <p className="line-clamp-1 text-xs text-muted-foreground">{row.original.reasoning_summary}</p>
        </div>
      ),
    },
    { accessorKey: "state", header: "State", cell: ({ row }) => <StatusBadge status={row.original.state} /> },
    { accessorKey: "priority", header: "Priority", cell: ({ row }) => <span className="capitalize">{row.original.priority}</span> },
    { accessorKey: "assignee", header: "Assignee", cell: ({ row }) => row.original.assignee ?? "Unassigned" },
    { accessorKey: "due_at", header: "Due", cell: ({ row }) => formatDate(row.original.due_at) },
    { accessorKey: "created_at", header: "Proposed", cell: ({ row }) => <time dateTime={row.original.created_at}>{formatDateTime(row.original.created_at)}</time> },
  ], []);

  if (!canReview) {
    return (
      <div className="space-y-5">
        <PageHeader description="Review proposed local workflow tasks before any state-changing action can execute." eyebrow="Human control" title="Approval queue" />
        <InlineBanner title="Reviewer role required" tone="info">Approval records are available only to reviewer and administrator accounts. Your viewer account can inspect its approved tasks instead.</InlineBanner>
      </div>
    );
  }
  if (approvals.isLoading) return <PageSkeleton />;
  if (approvals.isError) return <ErrorState error={approvals.error} onRetry={() => approvals.refetch()} />;

  const rows = approvals.data?.items ?? [];
  const total = approvals.data?.total ?? 0;
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + rows.length, total);
  return (
    <div className="space-y-5">
      <PageHeader description="Review immutable proposal bindings before an authorized decision may create one local task." eyebrow="Human control" title="Approval queue" />
      <OperationalNotice icon={<ClipboardCheck className="size-4" />} title="Approval boundary" tone="pending">
        Pending proposals cannot create tasks until an authorized, audited decision approves their bound evidence.
      </OperationalNotice>
      <div className={approvals.isPlaceholderData ? "opacity-60" : undefined}>
        <DataTable
          columns={columns}
          data={rows}
          empty={<EmptyState description="Action proposals appear here only after a workflow produces an evidence-bound request." icon={<ClipboardCheck aria-hidden className="size-6" />} title="No proposals need review" />}
          getRowId={(row) => row.id}
          mobileRow={(proposal) => (
            <MobileRecordCard>
              <div className="flex items-start gap-3">
                <h2 className="min-w-0 flex-1">
                  <OperationalLink className="max-w-full whitespace-normal text-left" href={`/approvals/${encodeURIComponent(proposal.id)}`} title={proposal.title}><span className="line-clamp-2">{proposal.title}</span></OperationalLink>
                </h2>
                <StatusBadge status={proposal.state} />
              </div>
              <p className="mt-1.5 line-clamp-1 text-sm text-muted-foreground">{proposal.reasoning_summary}</p>
              <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-border/80 pt-2 text-xs">
                <div className="flex min-w-0 gap-1"><dt className="text-muted-foreground">Assignee</dt><dd className="truncate font-semibold">{proposal.assignee ?? "Unassigned"}</dd></div>
                <div className="flex gap-1"><dt className="text-muted-foreground">Due</dt><dd className="font-semibold">{formatDate(proposal.due_at)}</dd></div>
                <div className="flex gap-1"><dt className="text-muted-foreground">Priority</dt><dd className="font-semibold capitalize">{proposal.priority}</dd></div>
              </dl>
            </MobileRecordCard>
          )}
        />
      </div>
      <OperationalPagination
        ariaLabel="Approval pagination"
        first={first}
        isFetching={approvals.isFetching}
        last={last}
        noun="proposals"
        onNext={() => setOffset((value) => value + PAGE_SIZE)}
        onPrevious={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
        pageSize={PAGE_SIZE}
        startOffset={offset}
        total={total}
      />
    </div>
  );
}
