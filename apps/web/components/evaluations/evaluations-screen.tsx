"use client";

import {
  EvaluationHistoryListSchema,
  type EvaluationHistoryEntry,
} from "@localguard/contracts";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { BadgeCheck } from "lucide-react";
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
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 15;

function booleanStatus(value: boolean | null | undefined): string {
  if (value == null) return "unavailable";
  return value ? "passed" : "failed";
}

function qualityStatus(entry: EvaluationHistoryEntry): string {
  if (entry.quality_passed == null) {
    return entry.runtime_provider === "deterministic" ? "not_applicable" : "unavailable";
  }
  return entry.quality_passed ? "passed" : "failed";
}

function caseCount(entry: EvaluationHistoryEntry): string {
  if (entry.completed_case_count == null || entry.case_count == null) return "Unavailable";
  return `${entry.completed_case_count}/${entry.case_count}`;
}

export function EvaluationsScreen() {
  const [offset, setOffset] = useState(0);
  const { user } = useAuth();
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  const parameters = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) });
  const filters = parameters.toString();
  const runs = useQuery({
    queryKey: queryKeys.evaluations(filters),
    queryFn: () => apiRequest(`/evaluations?${filters}`, EvaluationHistoryListSchema),
    enabled: canReview,
    placeholderData: keepPreviousData,
  });
  const columns = useMemo<Array<ColumnDef<EvaluationHistoryEntry>>>(() => [
    { accessorKey: "run_id", header: "Run", cell: ({ row }) => <OperationalLink className="max-w-64 truncate font-mono text-xs" href={`/evaluations/${encodeURIComponent(row.original.run_id)}`} title={row.original.run_id}>{row.original.run_id}</OperationalLink> },
    { accessorKey: "schema_version", header: "Schema", cell: ({ row }) => <div className="flex flex-col items-start gap-1"><span className="font-mono text-xs">{row.original.schema_version ?? "Unknown"}</span><StatusBadge status={row.original.comparability_status} /></div> },
    { accessorKey: "runtime_provider", header: "Runtime", cell: ({ row }) => <span className="capitalize">{row.original.runtime_provider ?? "Unavailable"}</span> },
    { id: "cases", header: "Cases", cell: ({ row }) => caseCount(row.original) },
    { id: "safety", header: "Safety", cell: ({ row }) => <StatusBadge status={booleanStatus(row.original.safety_passed)} /> },
    { id: "quality", header: "Quality", cell: ({ row }) => <StatusBadge status={qualityStatus(row.original)} /> },
    { id: "result", header: "Result", cell: ({ row }) => <StatusBadge status={booleanStatus(row.original.run_passed)} /> },
    { accessorKey: "integrity_status", header: "Integrity", cell: ({ row }) => <span title={row.original.integrity_note}><StatusBadge status={row.original.integrity_status} /></span> },
  ], []);

  if (!canReview) return <div className="space-y-5"><PageHeader description="Inspect generated, read-only benchmark evidence." eyebrow="Assurance" title="Evaluations" /><InlineBanner title="Reviewer role required" tone="info">Evaluation results are restricted to reviewer and administrator accounts.</InlineBanner></div>;
  if (runs.isLoading) return <PageSkeleton />;
  if (runs.isError) return <ErrorState error={runs.error} onRetry={() => runs.refetch()} />;
  const rows = runs.data?.items ?? [];
  const total = runs.data?.total ?? 0;
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + rows.length, total);
  return (
    <div className="space-y-5">
      <PageHeader description="Inspect integrity-validated evaluation artifacts generated from measured application behavior." eyebrow="Assurance" title="Evaluations" />
      <OperationalNotice icon={<BadgeCheck className="size-4" />} title="Evidence contract" tone="info">
        Deterministic runs prove safety invariants; Ollama runs also measure model quality. Non-comparable artifacts remain visible without comparable metrics.
      </OperationalNotice>
      <div className={runs.isPlaceholderData ? "opacity-60" : undefined}>
        <DataTable
          columns={columns}
          data={rows}
          empty={<EmptyState description="Run the checked evaluation workflow to produce the first read-only result artifact." icon={<BadgeCheck aria-hidden className="size-6" />} title="No evaluation runs yet" />}
          getRowId={(run) => run.run_id}
          wide
          mobileRow={(run) => (
            <MobileRecordCard>
              <div className="flex items-start gap-3">
                <OperationalLink className="min-w-0 max-w-full flex-1 truncate font-mono text-xs" href={`/evaluations/${encodeURIComponent(run.run_id)}`} title={run.run_id}>{run.run_id}</OperationalLink>
                <StatusBadge status={booleanStatus(run.run_passed)} />
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-1.5 border-t border-border/80 pt-2">
                <StatusBadge status={run.integrity_status} />
                <StatusBadge status={run.comparability_status} />
              </div>
              <p className="mt-1.5 text-xs capitalize text-muted-foreground">
                {run.runtime_provider ?? "Runtime unavailable"} · {caseCount(run)} cases · schema {run.schema_version ?? "unknown"}
              </p>
            </MobileRecordCard>
          )}
        />
      </div>
      <OperationalPagination
        ariaLabel="Evaluation pagination"
        first={first}
        isFetching={runs.isFetching}
        last={last}
        noun="runs"
        onNext={() => setOffset((value) => value + PAGE_SIZE)}
        onPrevious={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
        pageSize={PAGE_SIZE}
        startOffset={offset}
        total={total}
      />
    </div>
  );
}
