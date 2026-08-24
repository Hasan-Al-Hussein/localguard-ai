"use client";

import {
  DocumentDetailSchema,
  RevisionSectionSchema,
  type DocumentAnchor,
} from "@localguard/contracts";
import { useQuery } from "@tanstack/react-query";
import { ArrowLeft, FileText, History, ListTree, Tags } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useMemo, useRef, useState, type KeyboardEvent } from "react";
import { ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { formatBytes, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const mobileTabs = ["document", "index"] as const;
type MobileTab = (typeof mobileTabs)[number];

type CitationTarget = {
  revisionId: string;
  anchorKey: string;
  start: number;
  end: number;
};

function readOffset(raw: string | null): number | null {
  if (raw == null || !/^\d+$/.test(raw)) return null;
  const value = Number(raw);
  return Number.isSafeInteger(value) ? value : null;
}

function parseCitationTarget(search: URLSearchParams): CitationTarget | null {
  const revisionId = search.get("revision_id");
  const anchorKey = search.get("anchor");
  const start = readOffset(search.get("start"));
  const end = readOffset(search.get("end"));
  if (!revisionId || !anchorKey || start == null || end == null || start < 0 || end <= start || end > 1_000_000) {
    return null;
  }
  return { revisionId, anchorKey, start, end };
}

function matchesDeepLink(anchor: DocumentAnchor, search: URLSearchParams): boolean {
  const anchorKey = search.get("anchor");
  if (anchorKey) return anchor.stable_key === anchorKey || anchor.id === anchorKey;

  const page = Number(search.get("page"));
  if (Number.isFinite(page) && page > 0) return anchor.stable_key === `page:${page}`;

  const paragraph = Number(search.get("paragraph"));
  if (Number.isFinite(paragraph) && paragraph > 0) return anchor.stable_key.endsWith(`:paragraph:${paragraph}`);

  const line = Number(search.get("line"));
  if (Number.isFinite(line) && line > 0) {
    const match = /^lines:(\d+)-(\d+)$/.exec(anchor.stable_key);
    return Boolean(match && line >= Number(match[1]) && line <= Number(match[2]));
  }
  return false;
}

function anchorKindLabel(kind: string): string {
  if (kind === "pdf_page") return "PDF page";
  if (kind === "docx_paragraph") return "Word paragraph";
  if (kind === "text_lines") return "Text lines";
  return kind.replaceAll("_", " ");
}

export function DocumentViewerScreen({ documentId }: { documentId: string }) {
  const searchParams = useSearchParams();
  const searchKey = searchParams.toString();
  const pathname = usePathname();
  const router = useRouter();
  const [mobileTab, setMobileTab] = useState<MobileTab>("document");
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const citationTarget = useMemo(
    () => parseCitationTarget(new URLSearchParams(searchKey)),
    [searchKey],
  );
  const hasCitationParameters = ["revision_id", "anchor", "start", "end"].some((key) => searchParams.has(key));

  const document = useQuery({
    queryKey: queryKeys.document(documentId),
    queryFn: () => apiRequest(`/documents/${encodeURIComponent(documentId)}`, DocumentDetailSchema),
    refetchInterval: (query) => ["queued", "processing"].includes(query.state.data?.state ?? "") ? 2_000 : false,
  });

  const citation = useQuery({
    queryKey: citationTarget
      ? queryKeys.revisionSection(
          documentId,
          citationTarget.revisionId,
          citationTarget.anchorKey,
          citationTarget.start,
          citationTarget.end,
        )
      : ["document", documentId, "revision", "none"],
    queryFn: () => {
      if (!citationTarget) throw new Error("Citation target is not valid");
      const parameters = new URLSearchParams({
        start_offset: String(citationTarget.start),
        end_offset: String(citationTarget.end),
      });
      return apiRequest(
        `/documents/${encodeURIComponent(documentId)}/revisions/${encodeURIComponent(citationTarget.revisionId)}/anchors/${encodeURIComponent(citationTarget.anchorKey)}?${parameters.toString()}`,
        RevisionSectionSchema,
      );
    },
    enabled: Boolean(citationTarget),
    retry: false,
  });

  const targetAnchor = useMemo(() => {
    if (citationTarget) return null;
    return document.data?.anchors.find((anchor) => matchesDeepLink(anchor, searchParams)) ?? null;
  }, [citationTarget, document.data, searchParams]);

  useEffect(() => {
    if (!targetAnchor) return;
    const element = window.document.getElementById(`anchor-${targetAnchor.id}`);
    element?.scrollIntoView({ block: "center", behavior: "smooth" });
    element?.focus({ preventScroll: true });
  }, [targetAnchor]);

  function selectAnchor(anchor: DocumentAnchor) {
    const parameters = new URLSearchParams();
    parameters.set("anchor", anchor.stable_key);
    router.replace(`${pathname}?${parameters.toString()}`);
    setMobileTab("document");
  }

  function selectMobileTab(next: MobileTab) {
    setMobileTab(next);
  }

  function handleTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, current: MobileTab) {
    const currentIndex = mobileTabs.indexOf(current);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight") nextIndex = (currentIndex + 1) % mobileTabs.length;
    if (event.key === "ArrowLeft") nextIndex = (currentIndex - 1 + mobileTabs.length) % mobileTabs.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = mobileTabs.length - 1;
    if (nextIndex == null) return;
    event.preventDefault();
    const next = mobileTabs[nextIndex];
    setMobileTab(next);
    tabRefs.current[nextIndex]?.focus();
  }

  if (document.isLoading) return <PageSkeleton />;
  if (document.isError) return <ErrorState error={document.error} onRetry={() => document.refetch()} />;
  if (!document.data) return null;

  const detail = document.data;
  const revision = detail.current_revision;
  const description = revision
    ? `Revision ${revision.revision_number} · ${revision.original_filename} · ${formatBytes(revision.byte_size)} · Updated ${formatDateTime(detail.updated_at)}`
    : `No active revision · Updated ${formatDateTime(detail.updated_at)}`;
  const historicalCitation = Boolean(citation.data && citation.data.revision_id !== detail.current_revision_id);

  return (
    <div className="space-y-6">
      <Link className="button-base button-ghost inline-flex min-h-11 items-center gap-2 border px-3 text-sm font-semibold text-muted-foreground hover:text-brand" href="/documents"><ArrowLeft aria-hidden className="size-4" />Back to documents</Link>
      <PageHeader actions={<StatusBadge status={detail.state} />} description={description} eyebrow="Document evidence" title={detail.title} />

      {detail.state !== "ready" ? (
        <InlineBanner title={detail.state === "failed" ? "Processing failed" : "Document processing is still running"} tone={detail.state === "failed" ? "danger" : "info"}>
          {detail.state === "failed" ? "The local API did not return extracted anchors for this revision." : "Stored anchors will appear automatically after local extraction completes."}
        </InlineBanner>
      ) : null}

      {hasCitationParameters && !citationTarget ? (
        <InlineBanner title="This citation link is incomplete" tone="danger">A durable citation requires its revision, anchor, start offset, and end offset.</InlineBanner>
      ) : null}

      {citationTarget ? (
        <section aria-labelledby="cited-passage-heading" className="panel overflow-hidden ring-1 ring-evidence/10">
          <header className="flex flex-wrap items-start gap-3 border-b border-evidence/25 bg-evidence-soft px-5 py-4 sm:px-6">
            <span className="grid size-11 shrink-0 place-items-center rounded-xl bg-evidence text-white shadow-[0_8px_20px_rgb(11_122_112/0.2)]"><History aria-hidden className="size-5" /></span>
            <div className="min-w-0 flex-1">
              <h2 className="font-heading text-lg font-semibold" id="cited-passage-heading">Cited passage</h2>
              <p className="mt-1 text-sm text-muted-foreground">Resolved from the immutable revision and exact anchor-relative range stored with the answer.</p>
            </div>
            {historicalCitation ? <StatusBadge status="historical revision" /> : null}
          </header>
          <div className="p-5 sm:p-6">
            {citation.isLoading ? <p aria-live="polite" className="text-sm text-muted-foreground" role="status">Loading the cited revision…</p> : null}
            {citation.isError ? <ErrorState error={citation.error} onRetry={() => citation.refetch()} /> : null}
            {citation.data ? (
              <div className="evidence-rail rounded-r-xl bg-surface-raised px-4 py-4 shadow-[inset_0_1px_0_rgb(255_255_255/0.8)]" tabIndex={-1}>
                <p className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">{citation.data.anchor_label} · {anchorKindLabel(citation.data.kind)}</p>
                <p className="mt-3 text-[1.04rem] leading-8 whitespace-pre-wrap"><mark>{citation.data.text}</mark></p>
                <p className="mt-3 break-all font-mono text-[0.68rem] text-muted-foreground">Revision {citation.data.revision_id} · {citation.data.anchor_key} · offsets {citation.data.requested_start_offset}–{citation.data.requested_end_offset}</p>
              </div>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className="panel flex rounded-xl p-1 xl:hidden" role="tablist" aria-label="Document viewer sections">
        <button
          aria-controls="document-panel"
          aria-selected={mobileTab === "document"}
          className={cn("mode-option min-h-11 flex-1 rounded-lg px-3 text-sm font-semibold", mobileTab === "document" ? "bg-brand text-white shadow-md" : "text-muted-foreground")}
          id="document-tab"
          onClick={() => selectMobileTab("document")}
          onKeyDown={(event) => handleTabKeyDown(event, "document")}
          ref={(element) => { tabRefs.current[0] = element; }}
          role="tab"
          tabIndex={mobileTab === "document" ? 0 : -1}
          type="button"
        ><FileText aria-hidden className="mr-2 inline size-4" />Extracted text</button>
        <button
          aria-controls="index-panel"
          aria-selected={mobileTab === "index"}
          className={cn("mode-option min-h-11 flex-1 rounded-lg px-3 text-sm font-semibold", mobileTab === "index" ? "bg-brand text-white shadow-md" : "text-muted-foreground")}
          id="index-tab"
          onClick={() => selectMobileTab("index")}
          onKeyDown={(event) => handleTabKeyDown(event, "index")}
          ref={(element) => { tabRefs.current[1] = element; }}
          role="tab"
          tabIndex={mobileTab === "index" ? 0 : -1}
          type="button"
        ><Tags aria-hidden className="mr-2 inline size-4" />Anchor index ({detail.anchors.length})</button>
      </div>

      <div className="grid min-w-0 gap-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section
          aria-labelledby="document-tab"
          className={cn("min-w-0", mobileTab !== "document" && "hidden xl:block")}
          id="document-panel"
          role="tabpanel"
          tabIndex={0}
        >
          <div className="panel sticky top-[4.75rem] z-10 mb-4 flex flex-wrap items-center gap-2 px-4 py-3">
            <span className="flex items-center gap-2 text-sm font-semibold"><ListTree aria-hidden className="size-4 text-brand" />{detail.anchors.length} stored anchors</span>
            {revision ? <span className="ml-auto text-xs text-muted-foreground">{revision.extracted_characters?.toLocaleString() ?? "—"} extracted characters</span> : null}
          </div>

          <article className="document-paper panel mx-auto max-w-[820px] overflow-hidden bg-white">
            <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border bg-surface-raised px-6 py-3 text-xs font-semibold text-muted-foreground sm:px-10">
              <span>{revision?.original_filename ?? detail.title}</span><span>Extracted locally</span>
            </header>
            <div className="space-y-5 px-6 py-8 sm:px-10 sm:py-12">
              {detail.anchors.map((anchor) => {
                const highlighted = targetAnchor?.id === anchor.id;
                return (
                  <section
                    aria-label={highlighted ? "Selected passage" : undefined}
                    className={cn("scroll-mt-32", highlighted && "evidence-rail rounded-r-lg bg-evidence-soft/60 py-3 pr-3")}
                    id={`anchor-${anchor.id}`}
                    key={anchor.id}
                    tabIndex={highlighted ? -1 : undefined}
                  >
                    <div className="mb-2 flex flex-wrap items-center gap-2 text-[0.68rem] font-semibold tracking-wide text-muted-foreground uppercase"><span>{anchor.label}</span><span aria-hidden>·</span><span>{anchorKindLabel(anchor.kind)}</span></div>
                    <p className="text-[1.04rem] leading-8 whitespace-pre-wrap">{highlighted ? <mark>{anchor.text}</mark> : anchor.text}</p>
                    <p className="mt-2 font-mono text-[0.66rem] text-muted-foreground">{anchor.stable_key} · offsets {anchor.start_offset}–{anchor.end_offset}</p>
                  </section>
                );
              })}
              {detail.anchors.length === 0 ? <p className="text-sm text-muted-foreground">No extracted anchors are available for this revision.</p> : null}
            </div>
          </article>
        </section>

        <aside
          aria-labelledby="anchor-index-heading index-tab"
          className={cn("min-w-0", mobileTab !== "index" && "hidden xl:block")}
          id="index-panel"
          role="tabpanel"
          tabIndex={0}
        >
          <div className="panel overflow-hidden xl:sticky xl:top-[4.75rem] xl:max-h-[calc(100dvh-6.5rem)] xl:overflow-y-auto">
            <header className="border-b border-border px-5 py-4"><h2 className="font-heading text-lg font-semibold" id="anchor-index-heading">Anchor index</h2><p className="mt-1 text-sm text-muted-foreground">Stable source locations returned by the current revision.</p></header>
            {detail.anchors.length ? <ol className="divide-y divide-border">{detail.anchors.map((anchor) => <li key={anchor.id}><button aria-current={targetAnchor?.id === anchor.id ? "location" : undefined} className={cn("mode-option min-h-11 w-full px-5 py-4 text-left hover:bg-surface-raised", targetAnchor?.id === anchor.id && "bg-evidence-soft")} onClick={() => selectAnchor(anchor)} type="button"><span className="block text-sm font-semibold">{anchor.label}</span><span className="mt-1 block text-xs capitalize text-muted-foreground">{anchorKindLabel(anchor.kind)} · {anchor.stable_key}</span></button></li>)}</ol> : <p className="p-5 text-sm text-muted-foreground">No anchors are available yet.</p>}
          </div>
        </aside>
      </div>
    </div>
  );
}
