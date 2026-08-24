"use client";

import { ProposalsResponseSchema, type Proposal } from "@localguard/contracts";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ClipboardCheck } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { EmptyState, ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDate, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 25;

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
          <Link className="inline-flex min-h-11 items-center font-semibold text-brand hover:underline" href={`/approvals/${encodeURIComponent(row.original.id)}`}>{row.original.title}</Link>
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
      <div className="space-y-7">
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
    <div className="space-y-7">
      <PageHeader description="Review immutable proposal bindings before an authorized decision may create one local task." eyebrow="Human control" title="Approval queue" />
      <div className="rounded-xl border border-pending/30 bg-pending-soft p-4">
        <p className="flex items-center gap-2 text-sm font-semibold text-pending"><ClipboardCheck aria-hidden className="size-5" />A pending proposal is not a task. Approval is an explicit, audited boundary.</p>
      </div>
      <div className={approvals.isPlaceholderData ? "opacity-60" : undefined}>
        <DataTable
          columns={columns}
          data={rows}
          empty={<EmptyState description="Action proposals appear here only after a workflow produces an evidence-bound request." icon={<ClipboardCheck aria-hidden className="size-6" />} title="No proposals need review" />}
          getRowId={(row) => row.id}
          mobileRow={(proposal) => (
            <Link className="panel block min-h-11 p-4 transition-colors hover:border-brand/40" href={`/approvals/${encodeURIComponent(proposal.id)}`}>
              <div className="flex items-start gap-3"><h2 className="min-w-0 flex-1 font-semibold">{proposal.title}</h2><StatusBadge status={proposal.state} /></div>
              <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{proposal.reasoning_summary}</p>
              <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3 text-xs"><div><dt className="text-muted-foreground">Assignee</dt><dd className="mt-1 font-semibold">{proposal.assignee ?? "Unassigned"}</dd></div><div><dt className="text-muted-foreground">Due</dt><dd className="mt-1 font-semibold">{formatDate(proposal.due_at)}</dd></div></dl>
            </Link>
          )}
        />
      </div>
      {total > PAGE_SIZE ? (
        <nav aria-label="Approval pagination" className="flex flex-col gap-3 border-t border-border pt-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <p className="text-muted-foreground">Showing {first}–{last} of {total} proposals</p>
          <div className="flex gap-2"><Button disabled={offset === 0 || approvals.isFetching} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} variant="secondary">Previous</Button><Button disabled={offset + PAGE_SIZE >= total || approvals.isFetching} onClick={() => setOffset((value) => value + PAGE_SIZE)} variant="secondary">Next</Button></div>
        </nav>
      ) : null}
    </div>
  );
}
