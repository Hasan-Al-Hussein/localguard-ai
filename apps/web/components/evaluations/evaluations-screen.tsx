"use client";

import {
  EvaluationHistoryListSchema,
  type EvaluationHistoryEntry,
} from "@localguard/contracts";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { BadgeCheck } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { EmptyState, ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 25;

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
    { accessorKey: "run_id", header: "Run", cell: ({ row }) => <Link className="inline-flex min-h-11 max-w-64 items-center truncate font-mono text-xs font-semibold text-brand hover:underline" href={`/evaluations/${encodeURIComponent(row.original.run_id)}`}>{row.original.run_id}</Link> },
    { accessorKey: "schema_version", header: "Schema", cell: ({ row }) => <div><span className="font-mono text-xs">{row.original.schema_version ?? "Unknown"}</span><div className="mt-1"><StatusBadge status={row.original.comparability_status} /></div></div> },
    { accessorKey: "runtime_provider", header: "Runtime", cell: ({ row }) => <span className="capitalize">{row.original.runtime_provider ?? "Unavailable"}</span> },
    { id: "cases", header: "Cases", cell: ({ row }) => caseCount(row.original) },
    { id: "safety", header: "Safety", cell: ({ row }) => <StatusBadge status={booleanStatus(row.original.safety_passed)} /> },
    { id: "quality", header: "Quality", cell: ({ row }) => <StatusBadge status={qualityStatus(row.original)} /> },
    { id: "result", header: "Result", cell: ({ row }) => <StatusBadge status={booleanStatus(row.original.run_passed)} /> },
    { accessorKey: "integrity_status", header: "Integrity", cell: ({ row }) => <span title={row.original.integrity_note}><StatusBadge status={row.original.integrity_status} /></span> },
  ], []);

  if (!canReview) return <div className="space-y-7"><PageHeader description="Inspect generated, read-only benchmark evidence." eyebrow="Assurance" title="Evaluations" /><InlineBanner title="Reviewer role required" tone="info">Evaluation results are restricted to reviewer and administrator accounts.</InlineBanner></div>;
  if (runs.isLoading) return <PageSkeleton />;
  if (runs.isError) return <ErrorState error={runs.error} onRetry={() => runs.refetch()} />;
  const rows = runs.data?.items ?? [];
  const total = runs.data?.total ?? 0;
  return (
    <div className="space-y-7">
      <PageHeader description="Inspect integrity-validated evaluation artifacts generated from measured application behavior." eyebrow="Assurance" title="Evaluations" />
      <InlineBanner title="Interpret each artifact by its contract" tone="info">Deterministic runs prove the test path and safety invariants; only Ollama runs measure model quality. Legacy or integrity-failed records remain visible, but their metrics are not presented as comparable evidence.</InlineBanner>
      <div className={runs.isPlaceholderData ? "opacity-60" : undefined}><DataTable columns={columns} data={rows} empty={<EmptyState description="Run the checked evaluation workflow to produce the first read-only result artifact." icon={<BadgeCheck aria-hidden className="size-6" />} title="No evaluation runs yet" />} getRowId={(run) => run.run_id} mobileRow={(run) => <Link className="panel block min-h-11 p-4" href={`/evaluations/${encodeURIComponent(run.run_id)}`}><div className="flex items-start gap-3"><p className="min-w-0 flex-1 truncate font-mono text-xs font-semibold">{run.run_id}</p><StatusBadge status={booleanStatus(run.run_passed)} /></div><div className="mt-3 flex flex-wrap items-center gap-2"><StatusBadge status={run.integrity_status} /><StatusBadge status={run.comparability_status} /><span className="text-sm capitalize text-muted-foreground">{run.runtime_provider ?? "Runtime unavailable"} · {caseCount(run)} cases · schema {run.schema_version ?? "unknown"}</span></div></Link>} /></div>
      {total > PAGE_SIZE ? <nav aria-label="Evaluation pagination" className="flex items-center justify-between border-t border-border pt-4 text-sm"><p className="text-muted-foreground">Showing {offset + 1}–{Math.min(offset + rows.length, total)} of {total} runs</p><div className="flex gap-2"><Button disabled={offset === 0 || runs.isFetching} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} variant="secondary">Previous</Button><Button disabled={offset + PAGE_SIZE >= total || runs.isFetching} onClick={() => setOffset((value) => value + PAGE_SIZE)} variant="secondary">Next</Button></div></nav> : null}
    </div>
  );
}
