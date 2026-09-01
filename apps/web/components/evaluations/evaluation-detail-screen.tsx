"use client";

import {
  EvaluationHistoryDetailSchema,
  EvaluationRunSchema,
  type EvaluationHistoryDetail,
  type EvaluationHistoryEntry,
  type EvaluationRun,
} from "@localguard/contracts";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, BadgeCheck, Clock3, FlaskConical, ShieldCheck } from "lucide-react";
import { Link } from "@/components/ui/app-link";
import { useAuth } from "@/components/providers/auth-provider";
import { MetricsTable, type EvaluationMetric } from "@/components/evaluations/metrics-table";
import { EmptyState, ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDateTime, formatDuration, formatPercent } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

function resultStatus(value: boolean | null | undefined): string {
  if (value == null) return "unavailable";
  return value ? "passed" : "failed";
}

function finalProviderStage(result: EvaluationRun["results"][number]): string {
  const diagnostic = result.provider_diagnostics.at(-1);
  return diagnostic?.final_reason_code ?? diagnostic?.validation_stage ?? "No model call";
}

function integrityTone(
  status: EvaluationHistoryEntry["integrity_status"],
): "info" | "pending" | "danger" | "evidence" {
  if (status === "corrupt" || status === "hash_mismatch") return "danger";
  if (status === "unsupported_schema") return "pending";
  if (status === "run_verified") return "evidence";
  return "info";
}

function IntegrityNotice({ metadata }: { metadata: EvaluationHistoryEntry }) {
  return (
    <InlineBanner
      title={`Artifact integrity: ${metadata.integrity_status.replaceAll("_", " ")}`}
      tone={integrityTone(metadata.integrity_status)}
    >
      {metadata.integrity_note} {metadata.comparability_note}
    </InlineBanner>
  );
}

function HistoryOnlyDetail({ detail }: { detail: EvaluationHistoryDetail }) {
  const { metadata, legacy_run_metadata: legacy } = detail;
  const hasUnparsedCurrentRun = detail.current_run !== null;
  const cases = metadata.completed_case_count == null || metadata.case_count == null
    ? "Unavailable"
    : `${metadata.completed_case_count}/${metadata.case_count}`;

  return (
    <div className="space-y-6">
      <Link className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-semibold text-muted-foreground hover:text-brand" href="/evaluations"><ArrowLeft aria-hidden className="size-4" />Back to evaluations</Link>
      <PageHeader actions={<StatusBadge status={resultStatus(metadata.run_passed)} />} description={`${metadata.runtime_provider ?? "Unknown"} runtime · schema ${metadata.schema_version ?? "unknown"}`} eyebrow="Evaluation evidence" title={metadata.run_id} />
      <IntegrityNotice metadata={metadata} />
      {hasUnparsedCurrentRun ? <InlineBanner title="This run uses a newer detail contract" tone="pending">Its verified history metadata remains available, but this client cannot safely project the current-run metrics until the evaluator client contract is regenerated.</InlineBanner> : null}
      {legacy ? <InlineBanner title="Legacy metadata only" tone="pending">Schema {legacy.schema_version} predates the current metric contract. Timing metadata is shown below without projecting legacy values into current metrics.</InlineBanner> : null}
      <section aria-labelledby="stored-metadata-heading" className="panel p-5 sm:p-6">
        <h2 className="font-heading text-lg font-semibold" id="stored-metadata-heading">Stored artifact metadata</h2>
        <dl className="mt-5 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Cases completed</dt><dd className="mt-1 font-semibold">{cases}</dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Requested provider</dt><dd className="mt-1 font-semibold capitalize">{metadata.requested_provider ?? "Unavailable"}</dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Runtime provider</dt><dd className="mt-1 font-semibold capitalize">{metadata.runtime_provider ?? "Unavailable"}</dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Safety</dt><dd className="mt-2"><StatusBadge status={resultStatus(metadata.safety_passed)} /></dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Quality</dt><dd className="mt-2"><StatusBadge status={metadata.quality_passed == null && metadata.runtime_provider === "deterministic" ? "not_applicable" : resultStatus(metadata.quality_passed)} /></dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Overall result</dt><dd className="mt-2"><StatusBadge status={resultStatus(metadata.run_passed)} /></dd></div>
          <div className="sm:col-span-2 lg:col-span-3"><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Dataset</dt><dd className="mt-1 font-semibold">{metadata.dataset_version ?? "Unavailable"}</dd><dd className="mt-1 break-all font-mono text-xs text-muted-foreground">{metadata.dataset_sha256 ?? "Dataset digest unavailable"}</dd></div>
          <div className="sm:col-span-2 lg:col-span-3"><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Raw run digest</dt><dd className="mt-1 break-all font-mono text-xs">{metadata.raw_result_sha256 ?? "Unavailable"}</dd></div>
        </dl>
      </section>
      {legacy ? <section aria-labelledby="legacy-timing-heading" className="panel p-5 sm:p-6"><h2 className="font-heading text-lg font-semibold" id="legacy-timing-heading">Legacy run timing</h2><dl className="mt-5 grid gap-5 sm:grid-cols-2"><div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Started</dt><dd className="mt-1">{formatDateTime(legacy.started_at)}</dd></div><div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Completed</dt><dd className="mt-1">{formatDateTime(legacy.completed_at)}</dd></div><div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Wall clock</dt><dd className="mt-1">{formatDuration(legacy.wall_clock_ms)}</dd></div><div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Warmup</dt><dd className="mt-1">{legacy.warmup_completed ? "Completed" : "Not completed"}</dd></div></dl></section> : null}
    </div>
  );
}

export function EvaluationDetailScreen({ runId }: { runId: string }) {
  const { user } = useAuth();
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  const run = useQuery({ queryKey: queryKeys.evaluation(runId), queryFn: () => apiRequest(`/evaluations/${encodeURIComponent(runId)}`, EvaluationHistoryDetailSchema), enabled: canReview });
  if (!canReview) return <InlineBanner title="Reviewer role required" tone="info">Evaluation results are restricted to reviewer and administrator accounts.</InlineBanner>;
  if (run.isLoading) return <PageSkeleton />;
  if (run.isError) return <ErrorState error={run.error} onRetry={() => run.refetch()} />;
  if (!run.data) return null;
  const currentRun = run.data.current_run === null
    ? null
    : EvaluationRunSchema.safeParse(run.data.current_run);
  if (!currentRun?.success) return <HistoryOnlyDetail detail={run.data} />;
  const record = currentRun.data;
  const metadata = run.data.metadata;
  const aggregate = record.aggregate;
  const metrics: EvaluationMetric[] = [
    { label: "Retrieval recall at 1 (macro)", shortLabel: "R@1", value: aggregate.grounded_retrieval.macro_recall_at_k["1"] },
    { label: "Retrieval recall at 3 (macro)", shortLabel: "R@3", value: aggregate.grounded_retrieval.macro_recall_at_k["3"] },
    { label: "Retrieval recall at 5 (macro)", shortLabel: "R@5", value: aggregate.grounded_retrieval.macro_recall_at_k["5"] },
    { label: "Citation precision (macro)", shortLabel: "Citation", value: aggregate.citation_precision_macro },
    { label: "Grounding score", shortLabel: "Grounding", value: aggregate.grounding_score },
    { label: "Extraction F1", shortLabel: "Extract", value: aggregate.extraction.f1 },
    { label: "Tool selection accuracy", shortLabel: "Tools", value: aggregate.tool_selection_accuracy.value },
    { label: "Approval-gate compliance", shortLabel: "Approval", value: aggregate.approval_gate_compliance.value },
    { label: "Injection policy compliance", shortLabel: "Injection", value: aggregate.injection_policy_compliance.value },
    { label: "Schema validity", shortLabel: "Schema", value: aggregate.schema_validity.value },
  ];
  return (
    <div className="space-y-6">
      <Link className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-semibold text-muted-foreground hover:text-brand" href="/evaluations"><ArrowLeft aria-hidden className="size-4" />Back to evaluations</Link>
      <PageHeader actions={<StatusBadge status={resultStatus(metadata.run_passed)} />} description={`${record.runtime_provider} runtime · completed ${formatDateTime(record.completed_at)}`} eyebrow="Evaluation evidence" title={record.run_id} />
      <IntegrityNotice metadata={metadata} />
      {record.runtime_provider === "deterministic" ? <InlineBanner title="Safety-path evidence, not model quality" tone="info">This deterministic-provider run validates orchestration and safety invariants. Quality gates are intentionally not applicable.</InlineBanner> : null}
      {record.gates.failed_gates.length ? <InlineBanner title="One or more gates failed" tone="danger">{record.gates.failed_gates.join(", ")}</InlineBanner> : null}
      <section aria-label="Run summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="panel p-5"><BadgeCheck aria-hidden className="size-5 text-evidence" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Cases completed</p><p className="tabular-nums mt-1 font-heading text-2xl font-semibold">{aggregate.completed_case_count}/{aggregate.case_count}</p></div>
        <div className="panel p-5"><ShieldCheck aria-hidden className="size-5 text-pending" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Pre-approval tasks</p><p className="tabular-nums mt-1 font-heading text-2xl font-semibold">{aggregate.pre_approval_task_count}</p></div>
        <div className="panel p-5"><Clock3 aria-hidden className="size-5 text-brand" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Wall clock</p><p className="tabular-nums mt-1 font-heading text-2xl font-semibold">{formatDuration(record.wall_clock_ms)}</p></div>
        <div className="panel p-5"><FlaskConical aria-hidden className="size-5 text-info" /><p className="mt-4 text-xs font-semibold tracking-wide text-muted-foreground uppercase">Dataset</p><p className="mt-1 font-semibold">{record.dataset_version}</p><p className="mt-1 truncate font-mono text-xs text-muted-foreground">{record.dataset_sha256}</p></div>
      </section>
      <div className="grid gap-4 xl:grid-cols-2">
        <section aria-labelledby="runtime-identity-heading" className="panel p-5 sm:p-6">
          <h2 className="font-heading text-lg font-semibold" id="runtime-identity-heading">Runtime model identity</h2>
          <p className="mt-1 text-sm text-muted-foreground">Resolved names and immutable model manifests observed by this run.</p>
          <dl className="mt-5 grid gap-5 sm:grid-cols-2">
            <div>
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Chat model</dt>
              <dd className="mt-1 font-semibold">{record.runtime_model_identity.chat_model_name}</dd>
              <dd className="mt-1 break-all font-mono text-xs text-muted-foreground">{record.runtime_model_identity.chat_model_digest ?? "No digest for deterministic provider"}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Embedding model</dt>
              <dd className="mt-1 font-semibold">{record.runtime_model_identity.embedding_model_name}</dd>
              <dd className="mt-1 break-all font-mono text-xs text-muted-foreground">{record.runtime_model_identity.embedding_model_digest ?? "No digest for deterministic provider"}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Provider</dt>
              <dd className="mt-1 font-semibold capitalize">{record.runtime_model_identity.provider}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Runtime version</dt>
              <dd className="mt-1 font-mono text-sm">{record.runtime_model_identity.runtime_version}</dd>
            </div>
            <div>
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Raw response capture</dt>
              <dd className="mt-1 font-semibold">{record.provider_raw_response_capture_enabled ? "Enabled" : "Disabled"}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Structured extraction</dt>
              <dd className="mt-1 break-all font-mono text-sm">{record.structured_extraction_mode}</dd>
            </div>
            <div className="sm:col-span-2">
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Action proposals</dt>
              <dd className="mt-1 break-all font-mono text-sm">{record.action_proposal_mode}</dd>
            </div>
          </dl>
        </section>
        <section aria-labelledby="claim-provenance-heading" className="panel p-5 sm:p-6">
          <h2 className="font-heading text-lg font-semibold" id="claim-provenance-heading">Claim provenance</h2>
          <p className="mt-1 text-sm text-muted-foreground">Structured claims attributed to the model, the deterministic test provider, or a disclosed evidence normalizer.</p>
          <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3">
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">All claims</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.claim_provenance.total_claim_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Model claims</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.claim_provenance.model_claim_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Evidence-derived claims</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.claim_provenance.deterministic_normalizer_claim_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Test-provider claims</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.claim_provenance.deterministic_test_provider_claim_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Claim-bearing cases</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.claim_provenance.claim_bearing_case_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Derived case rate</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{formatPercent(record.claim_provenance.deterministic_normalizer_case_rate)}</dd></div>
          </dl>
          <p className="mt-5 border-t border-border pt-4 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">Evidence-derived cases:</span>{" "}
            {record.claim_provenance.deterministic_normalizer_case_ids.length
              ? record.claim_provenance.deterministic_normalizer_case_ids.join(", ")
              : "None"}
          </p>
        </section>
        <section aria-labelledby="finding-provenance-heading" className="panel p-5 sm:p-6">
          <h2 className="font-heading text-lg font-semibold" id="finding-provenance-heading">Finding provenance</h2>
          <p className="mt-1 text-sm text-muted-foreground">Structured findings attributed to the model, deterministic test path, or exact evidence normalizer.</p>
          <dl className="mt-5 grid grid-cols-2 gap-5 sm:grid-cols-3">
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">All findings</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.finding_provenance.total_finding_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Model findings</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.finding_provenance.model_finding_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Evidence-derived</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.finding_provenance.deterministic_normalizer_finding_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Test-provider</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.finding_provenance.deterministic_test_provider_finding_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Finding cases</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{record.finding_provenance.finding_bearing_case_count}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Derived case rate</dt><dd className="tabular-nums mt-1 text-xl font-semibold">{formatPercent(record.finding_provenance.deterministic_normalizer_case_rate)}</dd></div>
          </dl>
          <p className="mt-5 border-t border-border pt-4 text-sm text-muted-foreground">
            <span className="font-semibold text-foreground">Evidence-derived cases:</span>{" "}
            {record.finding_provenance.deterministic_normalizer_case_ids.length
              ? record.finding_provenance.deterministic_normalizer_case_ids.join(", ")
              : "None"}
          </p>
        </section>
      </div>
      <section aria-labelledby="corpus-integrity-heading" className="panel p-5 sm:p-6">
        <h2 className="font-heading text-lg font-semibold" id="corpus-integrity-heading">Corpus integrity</h2>
        <p className="mt-1 text-sm text-muted-foreground">Raw SHA-256 bindings for the measured cases and both sides of the synthetic document bundle.</p>
        <dl className="mt-5 grid gap-5 lg:grid-cols-2">
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Cases</dt><dd className="mt-1 break-all font-mono text-xs">{record.cases_sha256}</dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Corpus bundle</dt><dd className="mt-1 break-all font-mono text-xs">{record.corpus_bundle_sha256}</dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Canonical source manifest</dt><dd className="mt-1 break-all font-mono text-xs">{record.canonical_manifest_sha256}</dd></div>
          <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Generated fixture manifest</dt><dd className="mt-1 break-all font-mono text-xs">{record.generated_fixture_manifest_sha256}</dd></div>
        </dl>
      </section>
      <MetricsTable metrics={metrics} />
      <section className="panel overflow-hidden" aria-labelledby="case-results-heading">
        <header className="border-b border-border px-5 py-4 sm:px-6">
          <h2 className="font-heading text-lg font-semibold" id="case-results-heading">Case results</h2>
          <p className="mt-1 text-sm text-muted-foreground">Every measured case, provider-call count, final validation stage, and execution failure.</p>
        </header>
        {record.results.length ? (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[64rem] text-left text-sm">
              <thead className="bg-surface-raised text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                <tr>
                  <th className="px-5 py-3" scope="col">Case</th>
                  <th className="px-5 py-3" scope="col">Category</th>
                  <th className="px-5 py-3" scope="col">Task type</th>
                  <th className="px-5 py-3" scope="col">Execution</th>
                  <th className="px-5 py-3 text-right" scope="col">Provider attempts</th>
                  <th className="px-5 py-3" scope="col">Final validation</th>
                  <th className="px-5 py-3 text-right" scope="col">Latency</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {record.results.map((result) => (
                  <tr key={result.case_id}>
                    <th className="px-5 py-3 font-mono text-xs" scope="row">{result.case_id}</th>
                    <td className="px-5 py-3 capitalize">{result.category}</td>
                    <td className="px-5 py-3">{result.task_type}</td>
                    <td className="px-5 py-3">{result.failure ? <span className="text-danger"><strong>{result.failure.code}</strong><span className="mt-1 block max-w-lg text-xs">{result.failure.message}</span></span> : <StatusBadge status="measured" />}</td>
                    <td className="tabular-nums px-5 py-3 text-right">{result.provider_diagnostics.length}</td>
                    <td className="px-5 py-3 font-mono text-xs">{finalProviderStage(result)}</td>
                    <td className="tabular-nums px-5 py-3 text-right">{formatDuration(result.wall_clock_ms)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-5"><EmptyState description="This run contains no case records." title="No case results" /></div>
        )}
      </section>
      <p className="break-all font-mono text-xs text-muted-foreground">Schema {record.schema_version} · requested {record.requested_provider} · capabilities {record.system_capabilities.join(", ")}</p>
    </div>
  );
}
