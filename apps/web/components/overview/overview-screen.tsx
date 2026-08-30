"use client";

import { OverviewResponseSchema, type EvaluationOverview } from "@localguard/contracts";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, CalendarClock, Check, CircleAlert, CircleDotDashed, ClipboardCheck, FileCheck2, Files, MessagesSquare, ShieldCheck } from "lucide-react";
import { motion, useReducedMotion } from "motion/react";
import Link from "next/link";
import { useState } from "react";
import { ProofGateMark } from "@/components/brand/proof-gate-mark";
import { ProofCoreScene } from "@/components/effects/proof-core-scene";
import { useAuth } from "@/components/providers/auth-provider";
import { EmptyState, ErrorState, PageSkeleton } from "@/components/ui/async-state";
import { MetricCard } from "@/components/ui/metric-card";
import { ScrollReveal, ScrollRevealGroup, ScrollRevealItem } from "@/components/ui/scroll-reveal";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDate, formatDateTime } from "@/lib/format";
import { cascadeVariants, revealFromRightVariants, revealVariants } from "@/lib/motion";
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
  const [showAllActivity, setShowAllActivity] = useState(false);
  const reduceMotion = useReducedMotion();
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
  const visibleActivity = canReview || !showAllActivity ? data.recent_activity.slice(0, 5) : data.recent_activity;
  const readyPercent = data.documents_total ? Math.round((data.documents_ready / data.documents_total) * 100) : 0;
  const evaluation = data.evaluation_summary;
  return (
    <div className="overview-screen space-y-6">
      <motion.section animate="visible" aria-labelledby="overview-title" className="overview-command-hero overview-command-hero--compact" initial={reduceMotion ? false : "hidden"} variants={revealVariants}>
        <motion.div className="overview-command-copy overview-command-copy--compact" variants={cascadeVariants}>
          <motion.div className="overview-kicker" variants={revealVariants}><ProofGateMark className="size-4" />Local intelligence plane</motion.div>
          <motion.h1 id="overview-title" variants={revealVariants}>Overview</motion.h1>
          <motion.p className="overview-command-headline" variants={revealVariants}>Every claim connected. Every action gated.</motion.p>
          <motion.p className="overview-command-description" variants={revealVariants}>Index private documents, open exact source proof, and keep every proposed action behind human review.</motion.p>
          <motion.div className="overview-command-actions" variants={revealVariants}>
            <Link className="command-primary" href="/ask">Ask the evidence <ArrowRight aria-hidden className="size-4" /></Link>
            <Link className="command-secondary" href="/documents">Open document vault</Link>
          </motion.div>
          <motion.ol aria-label="Evidence pipeline" className="overview-pipeline overview-pipeline--compact" variants={revealVariants}>
            {["Index", "Retrieve", "Cite", "Approve"].map((step, index) => <li key={step}><span><Check aria-hidden className="size-3" /></span><small>0{index + 1}</small>{step}</li>)}
          </motion.ol>
        </motion.div>
        <motion.div className="overview-proof-core-shell" variants={revealFromRightVariants}><ProofCoreScene className="overview-proof-core" compact priority /></motion.div>
        <div className="overview-live-strip overview-live-strip--compact">
          <span><i className="bg-[#52e0c4]" />System plane <strong>local</strong></span>
          <span>Documents ready <strong>{readyPercent}%</strong></span>
          <span>Awaiting human gate <strong>{data.pending_approvals}</strong></span>
        </div>
      </motion.section>

      <ScrollRevealGroup className="overview-metrics grid grid-cols-2 gap-3 sm:gap-4 xl:grid-cols-3 2xl:grid-cols-6" label="Workspace metrics">
        <ScrollRevealItem className="h-full"><MetricCard href="/documents" icon={<Files aria-hidden className="size-5" />} label="Documents" value={data.documents_total} /></ScrollRevealItem>
        <ScrollRevealItem className="h-full"><MetricCard href="/documents" icon={<FileCheck2 aria-hidden className="size-5" />} label="Ready" tone="evidence" value={data.documents_ready} /></ScrollRevealItem>
        <ScrollRevealItem className="h-full"><MetricCard href="/documents" icon={<CircleDotDashed aria-hidden className="size-5" />} label="Processing" tone="pending" value={data.documents_processing} /></ScrollRevealItem>
        <ScrollRevealItem className="h-full"><MetricCard href="/ask" icon={<MessagesSquare aria-hidden className="size-5" />} label="Questions" value={data.questions_total} /></ScrollRevealItem>
        <ScrollRevealItem className="h-full"><MetricCard detail="Background jobs that returned a failure" href="/ask" icon={<CircleAlert aria-hidden className="size-5" />} label="Question failures" tone={data.questions_failed ? "danger" : "evidence"} value={data.questions_failed} /></ScrollRevealItem>
        <ScrollRevealItem className="h-full"><MetricCard detail="Evidence-bound proposals awaiting a decision" href={canReview ? "/approvals" : undefined} icon={<ClipboardCheck aria-hidden className="size-5" />} label="Pending approvals" tone={data.pending_approvals ? "pending" : "evidence"} value={data.pending_approvals} /></ScrollRevealItem>
      </ScrollRevealGroup>

      <ScrollReveal className="overview-snapshot-grid grid gap-5 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <section className="overview-deadlines-panel panel overflow-hidden" aria-labelledby="deadlines-heading">
          <header className="overview-section-header flex items-center gap-3 border-b border-border px-5 py-3.5 sm:px-6"><CalendarClock aria-hidden className="size-5 text-pending" /><div><h2 className="font-heading text-lg font-semibold" id="deadlines-heading">Extracted deadlines</h2><p className="mt-0.5 text-sm text-muted-foreground">Structured dates from grounded workflows.</p></div></header>
          {data.extracted_deadlines.length ? (
            <ol className="divide-y divide-border">
              {data.extracted_deadlines.map((deadline) => (
                <li className="list-action px-5 py-3 sm:px-6" key={deadline.id}>
                  <div className="flex items-start gap-3"><p className="min-w-0 flex-1 text-sm font-semibold">{deadline.summary}</p>{deadline.severity ? <StatusBadge status={deadline.severity} /> : null}</div>
                  <p className="mt-1.5 text-xs text-muted-foreground">Due {formatDate(deadline.due_date)}</p>
                </li>
              ))}
            </ol>
          ) : (
            <div className="overview-inline-empty flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <div className="flex items-center gap-3">
                <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-pending-soft text-pending"><CalendarClock aria-hidden className="size-4" /></span>
                <div><p className="text-sm font-semibold">No deadlines extracted yet</p><p className="mt-0.5 text-xs text-muted-foreground">Ask the evidence for a documented due date or obligation.</p></div>
              </div>
              <Link className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" href="/ask">Find a deadline <ArrowRight aria-hidden className="size-4" /></Link>
            </div>
          )}
        </section>

        <section className="overview-evaluation-panel panel overflow-hidden" aria-labelledby="assurance-heading">
          <header className="overview-section-header flex items-center gap-3 border-b border-border px-5 py-3.5 sm:px-6"><ShieldCheck aria-hidden className="size-5 text-evidence" /><div><h2 className="font-heading text-lg font-semibold" id="assurance-heading">Latest evaluation</h2><p className="mt-0.5 text-sm text-muted-foreground">Read-only assurance from the latest measured run.</p></div></header>
          {evaluation ? (
            <div className="evaluation-snapshot p-5 sm:p-6">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div><p className="text-xs font-semibold tracking-[0.1em] text-muted-foreground uppercase">Case coverage</p><p className="mt-1 font-heading text-2xl font-semibold">{evaluationCases(evaluation)}</p></div>
                <StatusBadge status={evaluationStatus(evaluation.run_passed)} />
              </div>
              <dl className="evaluation-status-grid mt-4 grid grid-cols-3 gap-2 text-sm">
                <div className="rounded-lg border border-border bg-surface-muted px-3 py-2.5"><dt className="text-xs text-muted-foreground">Integrity</dt><dd className="mt-1.5"><StatusBadge status={evaluation.integrity_status} /></dd></div>
                <div className="rounded-lg border border-border bg-surface-muted px-3 py-2.5"><dt className="text-xs text-muted-foreground">Safety</dt><dd className="mt-1.5"><StatusBadge status={evaluationStatus(evaluation.safety_passed)} /></dd></div>
                <div className="rounded-lg border border-border bg-surface-muted px-3 py-2.5"><dt className="text-xs text-muted-foreground">Quality</dt><dd className="mt-1.5"><StatusBadge status={evaluation.quality_passed == null && evaluation.runtime_provider === "deterministic" ? "not_applicable" : evaluationStatus(evaluation.quality_passed)} /></dd></div>
              </dl>
              <dl className="mt-4 flex flex-wrap gap-x-5 gap-y-2 text-xs text-muted-foreground"><div className="flex gap-1.5"><dt>Runtime</dt><dd className="font-mono capitalize text-foreground">{evaluation.runtime_provider ?? "unavailable"}</dd></div><div className="flex gap-1.5"><dt>Schema</dt><dd className="font-mono text-foreground">{evaluation.schema_version ?? "unknown"}</dd></div></dl>
              {(evaluation.integrity_note || evaluation.comparability_note) ? <div className="evaluation-notes mt-4 border-l-2 border-evidence/40 pl-3 text-sm text-muted-foreground">{evaluation.integrity_note ? <p>{evaluation.integrity_note}</p> : null}{evaluation.comparability_note ? <p className="mt-1.5">{evaluation.comparability_note}</p> : null}</div> : null}
              {canReview ? <Link className="mt-3 inline-flex min-h-11 items-center rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" href={`/evaluations/${encodeURIComponent(evaluation.run_id)}`}>Open evaluation record <ArrowRight aria-hidden className="ml-1.5 size-4" /></Link> : null}
            </div>
          ) : (
            <div className="overview-inline-empty flex flex-col gap-3 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6"><p className="text-sm text-muted-foreground">No evaluation artifacts are available.</p>{canReview ? <Link className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" href="/evaluations">View evaluations <ArrowRight aria-hidden className="size-4" /></Link> : null}</div>
          )}
        </section>
      </ScrollReveal>

      <ScrollReveal className="overview-operations-grid grid gap-5 xl:grid-cols-2">
        <section className="panel overflow-hidden" aria-labelledby="recent-documents-heading">
          <div className="overview-section-header flex items-center justify-between gap-3 border-b border-border px-5 py-3.5 sm:px-6">
            <div>
              <h2 className="font-heading text-lg font-semibold" id="recent-documents-heading">Recent documents</h2>
              <p className="mt-0.5 text-sm text-muted-foreground">Latest records in the local evidence vault.</p>
            </div>
            <Link className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" href="/documents">
              View library <ArrowRight aria-hidden className="size-4" />
            </Link>
          </div>
          {data.recent_documents.length ? (
            <ol className="divide-y divide-border">
              {data.recent_documents.map((document) => (
                <li className="list-action flex items-center gap-3 px-5 py-3 sm:px-6" key={document.id}>
                  <span className="grid size-9 shrink-0 place-items-center rounded-lg bg-surface-raised text-brand"><Files aria-hidden className="size-4" /></span>
                  <div className="min-w-0 flex-1">
                    <Link className="inline-flex min-h-11 max-w-full items-center truncate text-sm font-semibold text-brand hover:underline" href={`/documents/${encodeURIComponent(document.id)}`}>{document.title}</Link>
                    <p className="mt-0.5 text-xs text-muted-foreground">Updated <time dateTime={document.updated_at}>{formatDateTime(document.updated_at)}</time></p>
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
          <header className="overview-section-header flex items-center gap-3 border-b border-border px-5 py-3.5 sm:px-6"><Activity aria-hidden className="size-5 text-brand" /><div className="min-w-0 flex-1"><h2 className="font-heading text-lg font-semibold" id="recent-activity-heading">Recent activity</h2><p className="mt-0.5 text-sm text-muted-foreground">Redacted outcomes from the local audit stream.</p></div>{canReview ? <Link className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" href="/audit">View all <ArrowRight aria-hidden className="size-4" /></Link> : data.recent_activity.length > 5 ? <button aria-expanded={showAllActivity} className="inline-flex min-h-11 shrink-0 items-center rounded-md px-2 text-sm font-semibold text-brand hover:bg-surface-raised" onClick={() => setShowAllActivity((value) => !value)} type="button">{showAllActivity ? "Show less" : "Show all"}</button> : null}</header>
          {data.recent_activity.length ? <ol className="divide-y divide-border">{visibleActivity.map((event) => <li className="list-action flex flex-wrap items-center gap-3 px-5 py-3 sm:px-6" key={event.id}><div className="min-w-0 flex-1"><p className="text-sm font-semibold">{event.action}</p><p className="mt-0.5 text-xs text-muted-foreground">{event.resource_type} · {formatDateTime(event.occurred_at)}</p></div><StatusBadge status={event.outcome} /></li>)}</ol> : <p className="p-5 text-sm text-muted-foreground sm:p-6">No recent audit activity is available.</p>}
        </section>
      </ScrollReveal>
    </div>
  );
}
