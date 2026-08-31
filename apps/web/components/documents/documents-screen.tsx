"use client";

import {
  DocumentsResponseSchema,
  UploadAcceptedSchema,
  type DocumentSummary,
} from "@localguard/contracts";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { FilePlus2, RefreshCw, Search, Trash2, UploadCloud } from "lucide-react";
import { useMemo, useState } from "react";
import { z } from "zod";
import { useAuth } from "@/components/providers/auth-provider";
import { useNotice } from "@/components/providers/notice-provider";
import { EmptyState, ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { Modal } from "@/components/ui/modal";
import {
  MobileRecordCard,
  OperationalLink,
  OperationalPagination,
} from "@/components/ui/operational-list";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest, errorMessage } from "@/lib/api-client";
import { formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";
import { UploadDialog } from "./upload-dialog";

const activeStatuses = new Set(["queued", "processing"]);
const PAGE_SIZE = 15;

export function DocumentsScreen() {
  const [page, setPage] = useState(1);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<DocumentSummary | null>(null);
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const { notify } = useNotice();
  const canManage = user?.role === "reviewer" || user?.role === "admin";
  const canDelete = user?.role === "admin";
  const offset = (page - 1) * PAGE_SIZE;
  const filterString = `offset=${offset}&limit=${PAGE_SIZE}`;

  const documents = useQuery({
    queryKey: queryKeys.documents(filterString),
    queryFn: () => apiRequest(`/documents?${filterString}`, DocumentsResponseSchema),
    placeholderData: keepPreviousData,
    refetchInterval: (query) => query.state.data?.items.some((document) => activeStatuses.has(document.state)) ? 2_000 : false,
  });

  const reprocess = useMutation({
    mutationFn: (id: string) => apiRequest(`/documents/${encodeURIComponent(id)}/reprocess`, UploadAcceptedSchema, { method: "POST" }),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      notify("Document reprocessing was queued.");
    },
    onError: (error) => notify(errorMessage(error), "error"),
  });

  const remove = useMutation({
    mutationFn: (id: string) => apiRequest(`/documents/${encodeURIComponent(id)}`, z.object({ message: z.string() }), { method: "DELETE" }),
    onSuccess: async () => {
      setDeleteTarget(null);
      await queryClient.invalidateQueries({ queryKey: ["documents"] });
      notify("Document deleted.");
    },
    onError: (error) => notify(errorMessage(error), "error"),
  });
  const reprocessDocument = reprocess.mutate;
  const reprocessPending = reprocess.isPending;

  const columns = useMemo<Array<ColumnDef<DocumentSummary>>>(() => [
    {
      accessorKey: "title",
      header: "Document",
      cell: ({ row }) => (
        <div className="min-w-0">
          <OperationalLink className="max-w-sm truncate" href={`/documents/${encodeURIComponent(row.original.id)}`}>{row.original.title}</OperationalLink>
          <p className="mt-0.5 max-w-48 truncate font-mono text-xs text-muted-foreground" title={row.original.id}>{row.original.id}</p>
        </div>
      ),
    },
    { accessorKey: "state", header: "State", cell: ({ row }) => <StatusBadge status={row.original.state} /> },
    { accessorKey: "current_revision_id", header: "Current revision", cell: ({ row }) => row.original.current_revision_id ? <span className="block max-w-40 truncate font-mono text-xs" title={row.original.current_revision_id}>{row.original.current_revision_id}</span> : "Not available" },
    { accessorKey: "created_at", header: "Created", cell: ({ row }) => <time dateTime={row.original.created_at}>{formatDateTime(row.original.created_at)}</time> },
    { accessorKey: "updated_at", header: "Updated", cell: ({ row }) => <time dateTime={row.original.updated_at}>{formatDateTime(row.original.updated_at)}</time> },
    {
      id: "actions",
      header: "Actions",
      enableSorting: false,
      cell: ({ row }) => canManage ? (
        <div className="flex items-center justify-end gap-1">
          <button aria-label={`Reprocess ${row.original.title}`} className="icon-button grid size-11 place-items-center rounded-lg text-muted-foreground hover:bg-info-soft hover:text-info disabled:opacity-40" disabled={activeStatuses.has(row.original.state) || reprocessPending} onClick={() => reprocessDocument(row.original.id)} title="Reprocess" type="button"><RefreshCw aria-hidden className="size-4" /></button>
          {canDelete ? <button aria-label={`Delete ${row.original.title}`} className="icon-button grid size-11 place-items-center rounded-lg text-muted-foreground hover:bg-danger-soft hover:text-danger" onClick={() => setDeleteTarget(row.original)} title="Delete" type="button"><Trash2 aria-hidden className="size-4" /></button> : null}
        </div>
      ) : <span className="text-xs text-muted-foreground">Read only</span>,
    },
  ], [canDelete, canManage, reprocessDocument, reprocessPending]);

  if (documents.isLoading) return <PageSkeleton />;
  if (documents.isError) return <ErrorState error={documents.error} onRetry={() => documents.refetch()} />;

  const sourceRows = documents.data?.items ?? [];
  const rows = sourceRows.filter((document) =>
    (status === "all" || document.state === status) &&
    (!search.trim() || document.title.toLocaleLowerCase().includes(search.trim().toLocaleLowerCase())),
  );
  const total = documents.data?.total ?? 0;
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + sourceRows.length, total);

  return (
    <div className="space-y-5">
      <PageHeader
        actions={<Button disabled={!canManage} icon={<UploadCloud aria-hidden className="size-4" />} onClick={() => setUploadOpen(true)}>Upload document</Button>}
        description="Upload, process, and inspect synthetic operational documents without sending them off-device."
        eyebrow="Evidence library"
        title="Documents"
      />
      {!canManage ? <InlineBanner tone="info" title="Read-only access">Viewer accounts can inspect indexed evidence but cannot upload, reprocess, or delete documents.</InlineBanner> : null}

      <section aria-label="Document filters" className="document-filters flex flex-col gap-2 sm:flex-row">
        <label className="relative flex-1">
          <span className="sr-only">Filter the current document page</span>
          <Search aria-hidden className="pointer-events-none absolute top-1/2 left-3.5 size-4 -translate-y-1/2 text-muted-foreground" />
          <input className="min-h-11 w-full rounded-xl border border-border bg-surface pr-3 pl-10 text-base shadow-sm sm:text-sm" onChange={(event) => setSearch(event.target.value)} placeholder="Filter this page by title" type="search" value={search} />
        </label>
        <label>
          <span className="sr-only">Filter the current page by processing state</span>
          <select className="min-h-11 w-full rounded-xl border border-border bg-surface px-3 text-base shadow-sm sm:w-48 sm:text-sm" onChange={(event) => setStatus(event.target.value)} value={status}>
            <option value="all">All states</option><option value="queued">Queued</option><option value="processing">Processing</option><option value="ready">Ready</option><option value="failed">Failed</option>
          </select>
        </label>
      </section>

      <div className={documents.isPlaceholderData ? "opacity-60" : undefined}>
        <DataTable
          columns={columns}
          data={rows}
          empty={<EmptyState action={search || status !== "all" ? <Button onClick={() => { setSearch(""); setStatus("all"); }} variant="secondary">Clear page filters</Button> : canManage ? <Button icon={<FilePlus2 aria-hidden className="size-4" />} onClick={() => setUploadOpen(true)}>Upload a synthetic document</Button> : undefined} description={search || status !== "all" ? "No records on this server page match the local filter." : "Add the first PDF, DOCX, or TXT fixture to begin the cited-question workflow."} title={search || status !== "all" ? "No documents match on this page" : "No documents yet"} />}
          getRowId={(row) => row.id}
          mobileRow={(document) => (
            <MobileRecordCard>
              <div className="flex min-w-0 items-start gap-3">
                <div className="min-w-0 flex-1">
                  <OperationalLink className="max-w-full truncate" href={`/documents/${encodeURIComponent(document.id)}`}>{document.title}</OperationalLink>
                  <p className="mt-1 truncate font-mono text-[0.65rem] text-muted-foreground" title={document.id}>{document.id}</p>
                  <p className="mt-1 text-xs text-muted-foreground">Updated {formatDateTime(document.updated_at)}</p>
                </div>
                <StatusBadge status={document.state} />
              </div>
              {canManage ? (
                <div className="mt-2 flex min-h-11 justify-end gap-2 border-t border-border/80 pt-1.5">
                  <button aria-label={`Reprocess ${document.title}`} className="grid size-11 place-items-center self-center rounded-md text-muted-foreground hover:bg-info-soft hover:text-info disabled:opacity-40" disabled={activeStatuses.has(document.state) || reprocess.isPending} onClick={() => reprocess.mutate(document.id)} title="Reprocess" type="button"><RefreshCw aria-hidden className="size-4" /></button>
                  {canDelete ? <button aria-label={`Delete ${document.title}`} className="grid size-11 place-items-center self-center rounded-md text-muted-foreground hover:bg-danger-soft hover:text-danger" onClick={() => setDeleteTarget(document)} title="Delete" type="button"><Trash2 aria-hidden className="size-4" /></button> : null}
                </div>
              ) : null}
            </MobileRecordCard>
          )}
        />
      </div>

      <OperationalPagination
        ariaLabel="Document pagination"
        first={first}
        isFetching={documents.isFetching}
        last={last}
        noun="documents"
        onNext={() => setPage((value) => value + 1)}
        onPrevious={() => setPage((value) => Math.max(1, value - 1))}
        pageSize={PAGE_SIZE}
        startOffset={offset}
        summary={search.trim() || status !== "all" ? <>{rows.length} matches on this page · {total} total documents</> : undefined}
        total={total}
      />

      <UploadDialog onClose={() => setUploadOpen(false)} open={uploadOpen && canManage} />
      <Modal description="This removes the stored document from the active evidence library. Audit history remains." footer={<><Button disabled={remove.isPending} onClick={() => setDeleteTarget(null)} variant="secondary">Cancel</Button><Button isLoading={remove.isPending} onClick={() => deleteTarget && remove.mutate(deleteTarget.id)} variant="danger">Delete document</Button></>} onClose={() => setDeleteTarget(null)} open={Boolean(deleteTarget && canDelete)} title={`Delete ${deleteTarget?.title ?? "document"}?`}>
        <p className="text-sm text-muted-foreground">This action cannot be undone through the product interface.</p>
      </Modal>
    </div>
  );
}
