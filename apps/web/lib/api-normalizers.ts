import type { AnswerCitation } from "@localguard/contracts";

export type EvidenceReference = {
  id: string;
  documentId: string;
  documentLabel: string;
  locationLabel: string;
  quote: string;
  anchorKey?: string;
  revisionId?: string;
  startOffset?: number;
  endOffset?: number;
  pageNumber?: number;
  paragraphNumber?: number;
  lineStart?: number;
};

export function normalizeAnswerCitation(citation: AnswerCitation): EvidenceReference {
  return {
    id: citation.id,
    documentId: citation.document_id,
    documentLabel: `Document ${citation.document_id.slice(0, 8)}`,
    locationLabel: citation.anchor_label,
    quote: citation.quote,
    anchorKey: citation.anchor_key,
    revisionId: citation.revision_id,
    startOffset: citation.start_offset,
    endOffset: citation.end_offset,
  };
}
