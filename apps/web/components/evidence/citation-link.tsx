import type { AnswerCitation, EvidenceReference as WorkflowEvidenceReference } from "@localguard/contracts";
import { BookOpenText, ExternalLink } from "lucide-react";
import { Link } from "@/components/ui/app-link";
import {
  normalizeAnswerCitation,
  type EvidenceReference,
} from "@/lib/api-normalizers";
import { cn } from "@/lib/cn";

export function buildEvidenceHref(reference: EvidenceReference): string {
  const parameters = new URLSearchParams();
  if (reference.pageNumber) parameters.set("page", String(reference.pageNumber));
  if (reference.anchorKey) parameters.set("anchor", reference.anchorKey);
  else if (reference.paragraphNumber) parameters.set("paragraph", String(reference.paragraphNumber));
  else if (reference.lineStart) parameters.set("line", String(reference.lineStart));
  if (reference.revisionId) parameters.set("revision_id", reference.revisionId);
  if (reference.startOffset != null) parameters.set("start", String(reference.startOffset));
  if (reference.endOffset != null) parameters.set("end", String(reference.endOffset));
  const query = parameters.toString();
  return `/documents/${encodeURIComponent(reference.documentId)}${query ? `?${query}` : ""}`;
}

export function buildCitationHref(citation: AnswerCitation): string {
  return buildEvidenceHref(normalizeAnswerCitation(citation));
}

function EvidenceLink({ reference, compact = false, className }: { reference: EvidenceReference; compact?: boolean; className?: string }) {
  return (
    <Link
      aria-label={`Open ${reference.documentLabel}, ${reference.locationLabel}`}
      className={cn(
        "evidence-link group inline-flex min-h-11 max-w-full items-center gap-1.5 rounded-full border border-evidence/25 bg-evidence-soft px-3.5 py-1 text-xs font-semibold text-evidence",
        className,
      )}
      href={buildEvidenceHref(reference)}
    >
      <BookOpenText aria-hidden className="size-3.5 shrink-0" />
      <span className="truncate">{compact ? reference.locationLabel : `${reference.documentLabel} · ${reference.locationLabel}`}</span>
      <ExternalLink aria-hidden className="size-3 shrink-0 transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5" />
    </Link>
  );
}

function EvidenceQuote({ reference }: { reference: EvidenceReference }) {
  return (
    <figure className="evidence-rail rounded-r-lg bg-surface-raised px-4 py-3">
      <blockquote className="text-sm leading-6 text-foreground">“{reference.quote}”</blockquote>
      <figcaption className="mt-3"><EvidenceLink reference={reference} /></figcaption>
    </figure>
  );
}

export function AnswerCitationLink({ citation, compact = false }: { citation: AnswerCitation; compact?: boolean }) {
  return <EvidenceLink compact={compact} reference={normalizeAnswerCitation(citation)} />;
}

export function AnswerCitationEvidence({ citation }: { citation: AnswerCitation }) {
  return <EvidenceQuote reference={normalizeAnswerCitation(citation)} />;
}

function normalizeWorkflowEvidence(reference: WorkflowEvidenceReference): EvidenceReference | null {
  if (
    !reference.available
    || !reference.document_id
    || !reference.revision_id
    || !reference.anchor_key
    || reference.start_offset == null
    || reference.end_offset == null
  ) {
    return null;
  }
  return {
    id: reference.chunk_id,
    documentId: reference.document_id,
    documentLabel: reference.document_title ?? `Document ${reference.document_id.slice(0, 8)}`,
    locationLabel: reference.anchor_label ?? reference.anchor_key,
    quote: reference.excerpt ?? "The source passage is available in the stored revision.",
    anchorKey: reference.anchor_key,
    revisionId: reference.revision_id,
    startOffset: reference.start_offset,
    endOffset: reference.end_offset,
  };
}

export function WorkflowEvidence({ evidence }: { evidence: WorkflowEvidenceReference }) {
  const normalized = normalizeWorkflowEvidence(evidence);
  if (!normalized) {
    return (
      <div className="rounded-lg border border-border bg-surface-raised px-4 py-3">
        <p className="text-sm font-semibold text-muted-foreground">Source passage unavailable</p>
        <p className="mt-2 break-all font-mono text-xs text-muted-foreground">{evidence.chunk_id}</p>
      </div>
    );
  }
  return <EvidenceQuote reference={normalized} />;
}
