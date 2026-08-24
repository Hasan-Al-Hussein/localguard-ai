import type { Finding } from "@localguard/contracts";
import { ChevronDown, Fingerprint } from "lucide-react";
import { WorkflowEvidence } from "@/components/evidence/citation-link";

const originLabels: Record<Finding["origin"], string> = {
  model: "Model output",
  deterministic_test_provider: "Deterministic test provider",
  deterministic_evidence_normalizer: "Evidence-derived binding",
};

function bindingFields(finding: Finding): Array<{ label: string; value: string }> {
  const candidates = [
    { label: "Actor", value: finding.fields.actor ?? finding.responsible_party },
    { label: "Action", value: finding.fields.action },
    {
      label: "Deadline",
      value: finding.fields.deadline ?? finding.normalized_value ?? finding.due_date,
    },
  ];
  return candidates.filter((field): field is { label: string; value: string } => (
    typeof field.value === "string" && field.value.trim().length > 0
  ));
}

export function FindingCard({ finding }: { finding: Finding }) {
  const fields = bindingFields(finding);
  const originLabel = originLabels[finding.origin];
  const evidenceItems = finding.evidence ?? [];

  return (
    <article className="interactive-card rounded-xl border border-border bg-surface-raised p-4">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
          {finding.finding_type.replaceAll("_", " ")}
        </p>
        <span className="ml-auto inline-flex min-h-7 items-center gap-1.5 rounded-full bg-evidence-soft px-2.5 py-1 text-xs font-semibold text-evidence">
          <Fingerprint aria-hidden className="size-3.5" />
          {originLabel}
        </span>
      </div>
      <p className="mt-2 text-sm font-semibold">{finding.summary}</p>

      {fields.length ? (
        <dl className="mt-4 grid gap-3 border-t border-border pt-4 sm:grid-cols-3">
          {fields.map((field) => (
            <div key={field.label}>
              <dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                {field.label}
              </dt>
              <dd className="mt-1 break-words text-sm font-semibold">{field.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}

      <details className="group mt-4 border-t border-border pt-3">
        <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 text-sm font-semibold text-brand">
          <Fingerprint aria-hidden className="size-4" />
          Finding provenance
          <ChevronDown aria-hidden className="ml-auto size-4 transition-transform group-open:rotate-180" />
        </summary>
        <dl className="grid gap-3 pb-1 text-xs sm:grid-cols-2">
          <div><dt className="text-muted-foreground">Origin</dt><dd className="mt-1 font-semibold">{originLabel}</dd></div>
          <div><dt className="text-muted-foreground">Source markers</dt><dd className="mt-1 break-all font-mono">{finding.cited_marker_ids.length ? finding.cited_marker_ids.join(", ") : "None supplied"}</dd></div>
          <div><dt className="text-muted-foreground">Normalizer</dt><dd className="mt-1 break-all font-mono">{finding.normalizer_version ?? "Not applicable"}</dd></div>
          <div><dt className="text-muted-foreground">Derivation</dt><dd className="mt-1 break-all font-mono">{finding.derivation_reason ?? "Not applicable"}</dd></div>
          <div className="sm:col-span-2"><dt className="text-muted-foreground">Source binding SHA-256</dt><dd className="mt-1 break-all font-mono">{finding.source_marker_sha256 ?? "Not applicable"}</dd></div>
        </dl>
      </details>

      {evidenceItems.length ? (
        <div className="mt-4 space-y-3">
          {evidenceItems.map((evidence) => (
            <WorkflowEvidence evidence={evidence} key={evidence.chunk_id} />
          ))}
        </div>
      ) : null}
    </article>
  );
}
