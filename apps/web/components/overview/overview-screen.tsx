"use client";

import { OverviewResponseSchema, type EvaluationOverview } from "@localguard/contracts";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, CalendarClock, CircleAlert, CircleDotDashed, ClipboardCheck, FileCheck2, Files, MessagesSquare, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useAuth } from "@/components/providers/auth-provider";
import { EmptyState, ErrorState, PageSkeleton } from "@/components/ui/async-state";
import { MetricCard } from "@/components/ui/metric-card";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDate, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

function evaluationStatus(value: boolean | null): string {
  if (value == null) return "unavailable";
  return value ? "passed" : "failed";
}

function evaluationCases(summary: EvaluationOverview): string {
  if (summary.completed_case_count == null || summary.case_count == null) {
    return "Case metrics unavailable";
  }
  return `${summary.completed_case_count}/${summary.case_count} cases completed`;
}

export function OverviewScreen() {
  const { user } = useAuth();
  const overview = useQuery({
    queryKey: queryKeys.overview,
    queryFn: () => apiRequest("/overview", OverviewResponseSchema),
    staleTime: 15_000,
  });

  if (overview.isLoading) return <PageSkeleton />;
  if (overview.isError) return <ErrorState error={overview.error} onRetry={() => overview.refetch()} />;
  if (!overview.data) return null;

  const { data } = overview;
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  return (
    <div className="space-y-7">
      <PageHeader
        description="See what the local API has indexed and how many evidence questions have completed or failed."
        eyebrow="Operations"
        title="Overview"
      />

      <section aria-label="Workspace metrics" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <MetricCard href="/documents" icon={<Files aria-hidden className="size-5" />} label="Documents" value={data.documents_total} />
        <MetricCard href="/documents" icon={<FileCheck2 aria-hidden className="size-5" />} label="Ready" tone="evidence" value={data.documents_ready} />
        <MetricCard href="/documents" icon={<CircleDotDashed aria-hidden className="size-5" />} label="Processing" tone="pending" value={data.documents_processing} />
        <MetricCard href="/ask" icon={<MessagesSquare aria-hidden className="size-5" />} label="Questions" value={data.questions_total} />
        <MetricCard detail="Background jobs that returned a failure" href="/ask" icon={<CircleAlert aria-hidden className="size-5" />} label="Question failures" tone={data.questions_failed ? "danger" : "evidence"} value={data.questions_failed} />
        <MetricCard detail="Evidence-bound proposals awaiting a decision" href={canReview ? "/approvals" : undefined} icon={<ClipboardCheck aria-hidden className="size-5" />} label="Pending approvals" tone={data.pending_approvals ? "pending" : "evidence"} value={data.pending_approvals} />
      </section>

      <div className="grid gap-6 xl:grid-cols-2">
        <section className="panel overflow-hidden" aria-labelledby="deadlines-heading">
          <header className="flex items-center gap-3 border-b border-border px-5 py-4 sm:px-6"><CalendarClock aria-hidden className="size-5 text-pending" /><div><h2 className="font-heading text-lg font-semibold" id="deadlines-heading">Extracted deadlines</h2><p className="mt-1 text-sm text-muted-foreground">Latest structured deadlines from grounded workflows.</p></div></header>
          {data.extracted_deadlines.length ? <ol className="divide-y divide-border">{data.extracted_deadlines.map((deadline) => <li className="list-action px-5 py-4 sm:px-6" key={deadline.id}><div className="flex items-start gap-3"><p className="min-w-0 flex-1 text-sm font-semibold">{deadline.summary}</p>{deadline.severity ? <StatusBadge status={deadline.severity} /> : null}</div><p className="mt-2 text-xs text-muted-foreground">Due {formatDate(deadline.due_date)}</p></li>)}</ol> : <p className="p-5 text-sm text-muted-foreground sm:p-6">No extracted deadlines are available yet.</p>}
        </section>

        <section className="panel overflow-hidden" aria-labelledby="assurance-heading">
          <header className="flex items-center gap-3 border-b border-border px-5 py-4 sm:px-6"><ShieldCheck aria-hidden className="size-5 text-evidence" /><div><h2 className="font-heading text-lg font-semibold" id="assurance-heading">Latest evaluation</h2><p className="mt-1 text-sm text-muted-foreground">Read-only evidence from the most recent measured run.</p></div></header>
          {data.evaluation_summary ? <div className="p-5 sm:p-6"><div className="flex flex-wrap items-center gap-2"><StatusBadge status={data.evaluation_summary.integrity_status} /><StatusBadge status={evaluationStatus(data.evaluation_summary.run_passed)} /><span className="text-sm capitalize text-muted-foreground">{data.evaluation_summary.runtime_provider ?? "Runtime unavailable"}</span><span className="text-sm text-muted-foreground">· schema {data.evaluation_summary.schema_version ?? "unknown"}</span></div><p className="mt-4 font-heading text-2xl font-semibold">{evaluationCases(data.evaluation_summary)}</p><dl className="mt-4 grid grid-cols-3 gap-3 text-sm"><div><dt className="text-xs text-muted-foreground">Safety</dt><dd className="mt-1"><StatusBadge status={evaluationStatus(data.evaluation_summary.safety_passed)} /></dd></div><div><dt className="text-xs text-muted-foreground">Quality</dt><dd className="mt-1"><StatusBadge status={data.evaluation_summary.quality_passed == null && data.evaluation_summary.runtime_provider === "deterministic" ? "not_applicable" : evaluationStatus(data.evaluation_summary.quality_passed)} /></dd></div><div><dt className="text-xs text-muted-foreground">Result</dt><dd className="mt-1"><StatusBadge status={evaluationStatus(data.evaluation_summary.run_passed)} /></dd></div></dl><p className="mt-4 text-sm text-muted-foreground">{data.evaluation_summary.integrity_note}</p><p className="mt-2 text-sm text-muted-foreground">{data.evaluation_summary.comparability_note}</p>{canReview ? <Link className="mt-4 inline-flex min-h-11 items-center rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" href={`/evaluations/${encodeURIComponent(data.evaluation_summary.run_id)}`}>Open evaluation record <ArrowRight aria-hidden className="ml-1.5 size-4" /></Link> : null}</div> : <p className="p-5 text-sm text-muted-foreground sm:p-6">No evaluation artifacts are available.</p>}
        </section>
      </div>

      <section className="panel overflow-hidden" aria-labelledby="recent-documents-heading">
        <div className="flex items-center justify-between border-b border-border px-5 py-4 sm:px-6">
          <div>
            <h2 className="font-heading text-lg font-semibold" id="recent-documents-heading">Recent documents</h2>
            <p className="mt-1 text-sm text-muted-foreground">The latest records returned by the local document service.</p>
          </div>
          <Link className="inline-flex min-h-11 items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" href="/documents">
            View library <ArrowRight aria-hidden className="size-4" />
          </Link>
        </div>
        {data.recent_documents.length ? (
          <ol className="divide-y divide-border">
            {data.recent_documents.map((document) => (
              <li className="list-action flex items-center gap-3 px-5 py-4 sm:px-6" key={document.id}>
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-raised text-brand"><Files aria-hidden className="size-4" /></span>
                <div className="min-w-0 flex-1">
                  <Link className="inline-flex min-h-11 max-w-full items-center truncate text-sm font-semibold text-brand hover:underline" href={`/documents/${encodeURIComponent(document.id)}`}>{document.title}</Link>
                  <p className="mt-1 text-xs text-muted-foreground">Updated <time dateTime={document.updated_at}>{formatDateTime(document.updated_at)}</time></p>
                </div>
                <StatusBadge status={document.state} />
              </li>
            ))}
          </ol>
        ) : (
          <div className="p-5 sm:p-6"><EmptyState description="Upload a synthetic PDF, DOCX, or TXT file to create the first evidence record." title="No documents yet" /></div>
        )}
      </section>

      <section className="panel overflow-hidden" aria-labelledby="recent-activity-heading">
        <header className="flex items-center gap-3 border-b border-border px-5 py-4 sm:px-6"><Activity aria-hidden className="size-5 text-brand" /><div><h2 className="font-heading text-lg font-semibold" id="recent-activity-heading">Recent activity</h2><p className="mt-1 text-sm text-muted-foreground">Redacted operational outcomes from the local audit stream.</p></div></header>
        {data.recent_activity.length ? <ol className="divide-y divide-border">{data.recent_activity.map((event) => <li className="list-action flex flex-wrap items-center gap-3 px-5 py-4 sm:px-6" key={event.id}><div className="min-w-0 flex-1"><p className="text-sm font-semibold">{event.action}</p><p className="mt-1 text-xs text-muted-foreground">{event.resource_type} · {formatDateTime(event.occurred_at)}</p></div><StatusBadge status={event.outcome} /></li>)}</ol> : <p className="p-5 text-sm text-muted-foreground sm:p-6">No recent audit activity is available.</p>}
      </section>
    </div>
  );
}
