"use client";

import { TasksResponseSchema, type WorkflowTask } from "@localguard/contracts";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ListChecks } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";
import { EmptyState, ErrorState, PageSkeleton } from "@/components/ui/async-state";
import { Button } from "@/components/ui/button";
import { DataTable } from "@/components/ui/data-table";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDate, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 25;

export function TasksScreen() {
  const [offset, setOffset] = useState(0);
  const parameters = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) });
  const filters = parameters.toString();
  const tasks = useQuery({
    queryKey: queryKeys.tasks(filters),
    queryFn: () => apiRequest(`/tasks?${filters}`, TasksResponseSchema),
    placeholderData: keepPreviousData,
  });

  const columns = useMemo<Array<ColumnDef<WorkflowTask>>>(() => [
    {
      accessorKey: "title",
      header: "Task",
      cell: ({ row }) => (
        <div className="max-w-sm">
          <Link className="inline-flex min-h-11 items-center font-semibold text-brand hover:underline" href={`/tasks/${encodeURIComponent(row.original.id)}`}>{row.original.title}</Link>
          <p className="line-clamp-1 text-xs text-muted-foreground">{row.original.description}</p>
        </div>
      ),
    },
    { accessorKey: "state", header: "State", cell: ({ row }) => <StatusBadge status={row.original.state} /> },
    { accessorKey: "priority", header: "Priority", cell: ({ row }) => <span className="capitalize">{row.original.priority}</span> },
    { accessorKey: "assignee", header: "Assignee", cell: ({ row }) => row.original.assignee ?? "Unassigned" },
    { accessorKey: "due_at", header: "Due", cell: ({ row }) => formatDate(row.original.due_at) },
    { accessorKey: "updated_at", header: "Updated", cell: ({ row }) => formatDateTime(row.original.updated_at) },
  ], []);

  if (tasks.isLoading) return <PageSkeleton />;
  if (tasks.isError) return <ErrorState error={tasks.error} onRetry={() => tasks.refetch()} />;

  const rows = tasks.data?.items ?? [];
  const total = tasks.data?.total ?? 0;
  const first = total === 0 ? 0 : offset + 1;
  const last = Math.min(offset + rows.length, total);
  return (
    <div className="space-y-7">
      <PageHeader description="Track tasks created only through a bound human approval decision. Viewer accounts see tasks from their own workflows." eyebrow="Approved actions" title="Workflow tasks" />
      <div className={tasks.isPlaceholderData ? "opacity-60" : undefined}>
        <DataTable
          columns={columns}
          data={rows}
          empty={<EmptyState description="A task appears here only after an authorized reviewer approves a pending proposal and local execution succeeds." icon={<ListChecks aria-hidden className="size-6" />} title="No approved tasks yet" />}
          getRowId={(task) => task.id}
          mobileRow={(task) => (
            <Link className="panel block min-h-11 p-4 transition-colors hover:border-brand/40" href={`/tasks/${encodeURIComponent(task.id)}`}>
              <div className="flex items-start gap-3"><h2 className="min-w-0 flex-1 font-semibold">{task.title}</h2><StatusBadge status={task.state} /></div>
              <p className="mt-2 line-clamp-2 text-sm text-muted-foreground">{task.description}</p>
              <dl className="mt-4 grid grid-cols-2 gap-3 border-t border-border pt-3 text-xs"><div><dt className="text-muted-foreground">Assignee</dt><dd className="mt-1 font-semibold">{task.assignee ?? "Unassigned"}</dd></div><div><dt className="text-muted-foreground">Due</dt><dd className="mt-1 font-semibold">{formatDate(task.due_at)}</dd></div></dl>
              <p className="mt-3 text-xs text-muted-foreground">Updated {formatDateTime(task.updated_at)}</p>
            </Link>
          )}
        />
      </div>
      {total > PAGE_SIZE ? (
        <nav aria-label="Task pagination" className="flex flex-col gap-3 border-t border-border pt-4 text-sm sm:flex-row sm:items-center sm:justify-between">
          <p className="text-muted-foreground">Showing {first}–{last} of {total} tasks</p>
          <div className="flex gap-2"><Button disabled={offset === 0 || tasks.isFetching} onClick={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))} variant="secondary">Previous</Button><Button disabled={offset + PAGE_SIZE >= total || tasks.isFetching} onClick={() => setOffset((value) => value + PAGE_SIZE)} variant="secondary">Next</Button></div>
        </nav>
      ) : null}
    </div>
  );
}
