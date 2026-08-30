"use client";

import { TasksResponseSchema, type WorkflowTask } from "@localguard/contracts";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { ListChecks } from "lucide-react";
import { useMemo, useState } from "react";
import { EmptyState, ErrorState, PageSkeleton } from "@/components/ui/async-state";
import { DataTable } from "@/components/ui/data-table";
import {
  MobileRecordCard,
  OperationalLink,
  OperationalPagination,
} from "@/components/ui/operational-list";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest } from "@/lib/api-client";
import { formatDate, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const PAGE_SIZE = 15;

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
          <OperationalLink href={`/tasks/${encodeURIComponent(row.original.id)}`}>{row.original.title}</OperationalLink>
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
    <div className="space-y-5">
      <PageHeader description="Track tasks created only through a bound human approval decision. Viewer accounts see tasks from their own workflows." eyebrow="Approved actions" title="Workflow tasks" />
      <div className={tasks.isPlaceholderData ? "opacity-60" : undefined}>
        <DataTable
          columns={columns}
          data={rows}
          empty={<EmptyState description="A task appears here only after an authorized reviewer approves a pending proposal and local execution succeeds." icon={<ListChecks aria-hidden className="size-6" />} title="No approved tasks yet" />}
          getRowId={(task) => task.id}
          mobileRow={(task) => (
            <MobileRecordCard>
              <div className="flex items-start gap-3">
                <h2 className="min-w-0 flex-1">
                  <OperationalLink className="max-w-full whitespace-normal text-left" href={`/tasks/${encodeURIComponent(task.id)}`} title={task.title}><span className="line-clamp-2">{task.title}</span></OperationalLink>
                </h2>
                <StatusBadge status={task.state} />
              </div>
              <p className="mt-1.5 line-clamp-1 text-sm text-muted-foreground">{task.description}</p>
              <dl className="mt-2 flex flex-wrap gap-x-4 gap-y-1 border-t border-border/80 pt-2 text-xs">
                <div className="flex min-w-0 gap-1"><dt className="text-muted-foreground">Assignee</dt><dd className="truncate font-semibold">{task.assignee ?? "Unassigned"}</dd></div>
                <div className="flex gap-1"><dt className="text-muted-foreground">Due</dt><dd className="font-semibold">{formatDate(task.due_at)}</dd></div>
                <div className="flex gap-1"><dt className="text-muted-foreground">Priority</dt><dd className="font-semibold capitalize">{task.priority}</dd></div>
              </dl>
              <p className="mt-1.5 text-xs text-muted-foreground">Updated {formatDateTime(task.updated_at)}</p>
            </MobileRecordCard>
          )}
        />
      </div>
      <OperationalPagination
        ariaLabel="Task pagination"
        first={first}
        isFetching={tasks.isFetching}
        last={last}
        noun="tasks"
        onNext={() => setOffset((value) => value + PAGE_SIZE)}
        onPrevious={() => setOffset((value) => Math.max(0, value - PAGE_SIZE))}
        pageSize={PAGE_SIZE}
        startOffset={offset}
        total={total}
      />
    </div>
  );
}
