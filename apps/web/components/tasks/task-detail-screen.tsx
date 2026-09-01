"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { TaskPatchSchema, WorkflowTaskSchema } from "@localguard/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ClipboardCheck, FileCheck2, Save } from "lucide-react";
import { Link } from "@/components/ui/app-link";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { useAuth } from "@/components/providers/auth-provider";
import { useNotice } from "@/components/providers/notice-provider";
import { ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest, errorMessage } from "@/lib/api-client";
import { isPublicShowcase } from "@/lib/deployment-mode";
import { formatDate, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const TaskFormSchema = z.object({
  state: z.enum(["open", "in_progress", "completed", "cancelled"]),
  assignee: z.string().max(200),
  priority: z.enum(["low", "medium", "high", "critical"]),
  due_at: z.string(),
});
type TaskForm = z.infer<typeof TaskFormSchema>;

function toDateTimeLocal(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function TaskDetailScreen({ taskId }: { taskId: string }) {
  const { user } = useAuth();
  const { notify } = useNotice();
  const queryClient = useQueryClient();
  const task = useQuery({
    queryKey: queryKeys.task(taskId),
    queryFn: () => apiRequest(`/tasks/${encodeURIComponent(taskId)}`, WorkflowTaskSchema),
  });
  const canUpdate = !isPublicShowcase && (user?.role === "admin" || user?.role === "reviewer");
  const form = useForm<TaskForm>({
    resolver: zodResolver(TaskFormSchema),
    defaultValues: { state: "open", assignee: "", priority: "medium", due_at: "" },
  });

  useEffect(() => {
    if (!task.data) return;
    form.reset({
      state: task.data.state,
      assignee: task.data.assignee ?? "",
      priority: task.data.priority,
      due_at: toDateTimeLocal(task.data.due_at),
    });
  }, [form, task.data]);

  const updateTask = useMutation({
    mutationFn: (values: TaskForm) => {
      const body = TaskPatchSchema.parse({
        state: values.state,
        assignee: values.assignee.trim() || undefined,
        priority: values.priority,
        due_at: values.due_at ? new Date(values.due_at).toISOString() : undefined,
      });
      return apiRequest(`/tasks/${encodeURIComponent(taskId)}`, WorkflowTaskSchema, {
        method: "PATCH",
        body: JSON.stringify(body),
      });
    },
    onSuccess: async (updated) => {
      queryClient.setQueryData(queryKeys.task(taskId), updated);
      await queryClient.invalidateQueries({ queryKey: ["tasks"] });
      notify("Task changes were saved and recorded in the audit log.");
    },
    onError: (error) => notify(errorMessage(error), "error"),
  });

  if (task.isLoading) return <PageSkeleton />;
  if (task.isError) return <ErrorState error={task.error} onRetry={() => task.refetch()} />;
  if (!task.data) return null;

  const record = task.data;
  return (
    <div className="space-y-6">
      <Link className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-semibold text-muted-foreground hover:text-brand" href="/tasks"><ArrowLeft aria-hidden className="size-4" />Back to workflow tasks</Link>
      <PageHeader actions={<StatusBadge status={record.state} />} description={`${record.assignee ? `Assigned to ${record.assignee}` : "Unassigned"} · Updated ${formatDateTime(record.updated_at)}`} eyebrow="Approved task" title={record.title} />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.72fr)]">
        <div className="space-y-5">
          <section className="panel p-5 sm:p-6">
            <div className="flex items-center gap-2"><FileCheck2 aria-hidden className="size-5 text-brand" /><h2 className="font-heading text-lg font-semibold">Task record</h2></div>
            <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{record.description}</p>
            <dl className="mt-6 grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
              <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Assignee</dt><dd className="mt-1 font-semibold">{record.assignee ?? "Unassigned"}</dd></div>
              <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Priority</dt><dd className="mt-1 font-semibold capitalize">{record.priority}</dd></div>
              <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Due</dt><dd className="mt-1 font-semibold">{formatDate(record.due_at)}</dd></div>
              <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Created</dt><dd className="mt-1 font-semibold">{formatDateTime(record.created_at)}</dd></div>
            </dl>
          </section>

          <form className="panel p-5 sm:p-6" onSubmit={form.handleSubmit((values) => updateTask.mutate(values))}>
            <div className="flex items-center gap-2"><ClipboardCheck aria-hidden className="size-5 text-pending" /><h2 className="font-heading text-lg font-semibold">Update task</h2></div>
            <p className="mt-1 text-sm text-muted-foreground">Changes are explicit, role-gated, and appended to the audit log.</p>
            <fieldset className="mt-5 grid gap-4 sm:grid-cols-2" disabled={!canUpdate || updateTask.isPending}>
              <div><label className="text-sm font-semibold" htmlFor="task-state">State</label><select className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="task-state" {...form.register("state")}><option value="open">Open</option><option value="in_progress">In progress</option><option value="completed">Completed</option><option value="cancelled">Cancelled</option></select></div>
              <div><label className="text-sm font-semibold" htmlFor="task-priority">Priority</label><select className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="task-priority" {...form.register("priority")}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></div>
              <div><label className="text-sm font-semibold" htmlFor="task-assignee">Assignee</label><input className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="task-assignee" {...form.register("assignee")} /><p className="mt-1 text-xs text-muted-foreground">Blank retains the current value.</p></div>
              <div><label className="text-sm font-semibold" htmlFor="task-due">Due date and time</label><input className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="task-due" type="datetime-local" {...form.register("due_at")} /><p className="mt-1 text-xs text-muted-foreground">Blank retains the current value.</p></div>
            </fieldset>
            {!canUpdate ? <div className="mt-5"><InlineBanner tone="info" title={isPublicShowcase ? "Read-only demo record" : "Read-only access"}>{isPublicShowcase ? "Task editing is intentionally disabled in the public showcase. The private LocalGuard deployment records authorized changes in its audit log." : "Viewer accounts can inspect their task records but cannot change workflow state or assignment."}</InlineBanner></div> : null}
            {canUpdate ? <div className="mt-5 flex justify-end border-t border-border pt-5"><Button icon={<Save aria-hidden className="size-4" />} isLoading={updateTask.isPending} type="submit">Save changes</Button></div> : null}
          </form>
        </div>

        <aside className="space-y-5">
          <section className="panel p-5">
            <h2 className="font-heading text-lg font-semibold">Approval provenance</h2>
            <dl className="mt-4 space-y-3 text-sm">
              <div><dt className="text-muted-foreground">Approved proposal</dt><dd className="mt-1">{canUpdate ? <Link className="inline-flex min-h-11 items-center font-semibold text-brand hover:underline" href={`/approvals/${encodeURIComponent(record.proposal_id)}`}>Open proposal record</Link> : <span className="break-all font-mono text-xs">{record.proposal_id}</span>}</dd></div>
              <div><dt className="text-muted-foreground">Approval decision ID</dt><dd className="mt-1 break-all font-mono text-xs">{record.approval_decision_id}</dd></div>
              <div><dt className="text-muted-foreground">Created by user ID</dt><dd className="mt-1 break-all font-mono text-xs">{record.created_by_id}</dd></div>
            </dl>
          </section>
          <InlineBanner title="Evidence remains bound to the proposal" tone="evidence">{canUpdate ? "Open the proposal record to inspect the source passages and binding hashes used at approval time." : "The approval service preserves the proposal binding; proposal records are restricted to reviewer and administrator accounts."}</InlineBanner>
        </aside>
      </div>
    </div>
  );
}
