"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  ApprovalDecisionRequestSchema,
  DecisionAcceptedSchema,
  ProposalEditRequestSchema,
  ProposalSchema,
  type Proposal,
} from "@localguard/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, CheckCircle2, Fingerprint, PencilLine, ShieldAlert, XCircle } from "lucide-react";
import { Link } from "@/components/ui/app-link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { WorkflowEvidence } from "@/components/evidence/citation-link";
import { useAuth } from "@/components/providers/auth-provider";
import { useNotice } from "@/components/providers/notice-provider";
import { ErrorState, InlineBanner, PageSkeleton } from "@/components/ui/async-state";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest, errorMessage } from "@/lib/api-client";
import { isPublicShowcase } from "@/lib/deployment-mode";
import { formatDate, formatDateTime } from "@/lib/format";
import { queryKeys } from "@/lib/query-keys";

const RejectionSchema = z.object({ comment: z.string().trim().min(3, "Explain why this proposal is being rejected").max(1000) });
type Rejection = z.infer<typeof RejectionSchema>;

const EditFormSchema = z.object({
  title: z.string().trim().min(1).max(300),
  description: z.string().trim().min(1).max(2000),
  assignee: z.string().max(200),
  priority: z.enum(["low", "medium", "high", "critical"]),
  due_at: z.string(),
  reasoning_summary: z.string().trim().min(1).max(1000),
  comment: z.string().max(1000),
});
type EditForm = z.infer<typeof EditFormSchema>;

function binding(proposal: Proposal) {
  return {
    version: proposal.version,
    payload_hash: proposal.payload_hash,
    evidence_snapshot_hash: proposal.evidence_snapshot_hash,
  };
}

function toDateTimeLocal(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  const local = new Date(date.getTime() - date.getTimezoneOffset() * 60_000);
  return local.toISOString().slice(0, 16);
}

export function ApprovalDetailScreen({ approvalId }: { approvalId: string }) {
  const [rejectOpen, setRejectOpen] = useState(false);
  const [editOpen, setEditOpen] = useState(false);
  const { user } = useAuth();
  const { notify } = useNotice();
  const router = useRouter();
  const queryClient = useQueryClient();
  const canReview = user?.role === "admin" || user?.role === "reviewer";
  const canRevise = canReview && !isPublicShowcase;
  const approval = useQuery({
    queryKey: queryKeys.approval(approvalId),
    queryFn: () => apiRequest(`/approvals/${encodeURIComponent(approvalId)}`, ProposalSchema),
    enabled: canReview,
  });
  const rejectionForm = useForm<Rejection>({ resolver: zodResolver(RejectionSchema), defaultValues: { comment: "" } });
  const editForm = useForm<EditForm>({
    resolver: zodResolver(EditFormSchema),
    defaultValues: { title: "", description: "", assignee: "", priority: "medium", due_at: "", reasoning_summary: "", comment: "" },
  });

  useEffect(() => {
    if (!approval.data) return;
    editForm.reset({
      title: approval.data.title,
      description: approval.data.description,
      assignee: approval.data.assignee ?? "",
      priority: approval.data.priority,
      due_at: toDateTimeLocal(approval.data.due_at),
      reasoning_summary: approval.data.reasoning_summary,
      comment: "",
    });
  }, [approval.data, editForm]);

  const approve = useMutation({
    mutationFn: (proposal: Proposal) => apiRequest(
      `/approvals/${encodeURIComponent(approvalId)}/approve`,
      DecisionAcceptedSchema,
      { method: "POST", body: JSON.stringify(ApprovalDecisionRequestSchema.parse(binding(proposal))) },
    ),
    onSuccess: async (outcome) => {
      queryClient.setQueryData(queryKeys.approval(approvalId), outcome.proposal);
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ["approvals"] }),
        queryClient.invalidateQueries({ queryKey: ["tasks"] }),
      ]);
      if (isPublicShowcase) {
        notify("Demo approval recorded in this browser session.");
        return;
      }
      if (outcome.task) {
        notify("Proposal approved and exactly one local task was created.");
        router.push(`/tasks/${encodeURIComponent(outcome.task.id)}`);
      } else {
        notify("Approval was accepted. Task execution is being reconciled locally.");
        router.push("/tasks");
      }
    },
    onError: (error) => notify(errorMessage(error), "error"),
  });

  const reject = useMutation({
    mutationFn: ({ comment }: Rejection) => {
      if (!approval.data) throw new Error("Proposal is unavailable");
      const body = ApprovalDecisionRequestSchema.parse({ ...binding(approval.data), comment });
      return apiRequest(`/approvals/${encodeURIComponent(approvalId)}/reject`, DecisionAcceptedSchema, { method: "POST", body: JSON.stringify(body) });
    },
    onSuccess: async (outcome) => {
      setRejectOpen(false);
      rejectionForm.reset();
      queryClient.setQueryData(queryKeys.approval(approvalId), outcome.proposal);
      await queryClient.invalidateQueries({ queryKey: ["approvals"] });
      notify("Proposal rejected. No task was created.");
    },
    onError: (error) => notify(errorMessage(error), "error"),
  });

  const edit = useMutation({
    mutationFn: (values: EditForm) => {
      if (!approval.data) throw new Error("Proposal is unavailable");
      const body = ProposalEditRequestSchema.parse({
        ...binding(approval.data),
        title: values.title,
        description: values.description,
        assignee: values.assignee.trim() || undefined,
        priority: values.priority,
        due_at: values.due_at ? new Date(values.due_at).toISOString() : undefined,
        reasoning_summary: values.reasoning_summary,
        comment: values.comment.trim() || undefined,
      });
      return apiRequest(`/approvals/${encodeURIComponent(approvalId)}/edit`, DecisionAcceptedSchema, { method: "POST", body: JSON.stringify(body) });
    },
    onSuccess: async (outcome) => {
      setEditOpen(false);
      queryClient.setQueryData(queryKeys.approval(approvalId), outcome.proposal);
      await queryClient.invalidateQueries({ queryKey: ["approvals"] });
      if (outcome.replacement) {
        notify("The original proposal was invalidated and a new bound version is pending review.");
        router.push(`/approvals/${encodeURIComponent(outcome.replacement.id)}`);
      } else {
        notify("Proposal edit recorded.");
      }
    },
    onError: (error) => notify(errorMessage(error), "error"),
  });

  if (!canReview) {
    return (
      <div className="space-y-6">
        <Link className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-semibold text-muted-foreground hover:text-brand" href="/tasks"><ArrowLeft aria-hidden className="size-4" />Back to workflow tasks</Link>
        <InlineBanner title="Reviewer role required" tone="info">Proposal bindings and approval decisions are available only to reviewer and administrator accounts.</InlineBanner>
      </div>
    );
  }
  if (approval.isLoading) return <PageSkeleton />;
  if (approval.isError) return <ErrorState error={approval.error} onRetry={() => approval.refetch()} />;
  if (!approval.data) return null;

  const record = approval.data;
  const pending = record.state === "pending";

  return (
    <div className="space-y-6">
      <Link className="inline-flex min-h-11 items-center gap-2 rounded-md text-sm font-semibold text-muted-foreground hover:text-brand" href="/approvals"><ArrowLeft aria-hidden className="size-4" />Back to approvals</Link>
      <PageHeader actions={<StatusBadge status={record.state} />} description={`Version ${record.version} · Proposed ${formatDateTime(record.created_at)} · Expires ${formatDateTime(record.expires_at)}`} eyebrow="Human approval" title={record.title} />
      {pending ? (
        <InlineBanner title={isPublicShowcase ? "Browser-only approval simulation" : "Nothing has been created yet"} tone="pending">{isPublicShowcase ? "You can demonstrate the human gate below. The resulting synthetic task exists only in memory and disappears when this page is refreshed." : "The task described below remains a proposal. Approval revalidates its version, payload hash, and evidence snapshot before execution."}</InlineBanner>
      ) : (
        <InlineBanner title={`Proposal ${record.state.replaceAll("_", " ")}`} tone={record.state === "executed" || record.state === "approved" ? "evidence" : record.state === "rejected" || record.state === "failed" ? "danger" : "info"}>This proposal is no longer actionable. Its immutable decision boundary remains visible for review.</InlineBanner>
      )}

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(20rem,0.72fr)]">
        <section className="panel p-5 sm:p-6">
          <div className="flex items-center gap-2"><PencilLine aria-hidden className="size-5 text-brand" /><h2 className="font-heading text-lg font-semibold">Proposed task</h2></div>
          <p className="mt-4 whitespace-pre-wrap text-sm leading-6 text-muted-foreground">{record.description}</p>
          <dl className="mt-6 grid gap-4 border-t border-border pt-5 sm:grid-cols-2">
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Assignee</dt><dd className="mt-1 font-semibold">{record.assignee ?? "Unassigned"}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Priority</dt><dd className="mt-1 font-semibold capitalize">{record.priority}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Due</dt><dd className="mt-1 font-semibold">{formatDate(record.due_at)}</dd></div>
            <div><dt className="text-xs font-semibold tracking-wide text-muted-foreground uppercase">Kind</dt><dd className="mt-1 font-semibold">{record.kind}</dd></div>
          </dl>
          {pending ? (
            <div className="mt-6 flex flex-wrap justify-end gap-2 border-t border-border pt-5">
              {canRevise ? <Button disabled={approve.isPending || reject.isPending || edit.isPending} icon={<XCircle aria-hidden className="size-4" />} onClick={() => setRejectOpen(true)} variant="secondary">Reject</Button> : null}
              {canRevise ? <Button disabled={approve.isPending || reject.isPending || edit.isPending} icon={<PencilLine aria-hidden className="size-4" />} onClick={() => setEditOpen(true)} variant="secondary">Edit into new version</Button> : null}
              <Button icon={<CheckCircle2 aria-hidden className="size-4" />} isLoading={approve.isPending} onClick={() => approve.mutate(record)}>{isPublicShowcase ? "Simulate approval" : "Approve unchanged"}</Button>
            </div>
          ) : null}
        </section>

        <aside className="space-y-5">
          <section className="panel p-5"><div className="flex items-center gap-2"><ShieldAlert aria-hidden className="size-5 text-pending" /><h2 className="font-heading text-lg font-semibold">Reasoning summary</h2></div><p className="mt-3 text-sm leading-6 text-muted-foreground">{record.reasoning_summary}</p></section>
          <section className="panel overflow-hidden">
            <header className="border-b border-border px-5 py-4"><h2 className="font-heading text-lg font-semibold">Evidence snapshot</h2><p className="mt-1 text-sm text-muted-foreground">Each available passage opens its immutable revision and exact stored range.</p></header>
            <div className="space-y-4 p-5">{record.evidence?.length ? record.evidence.map((evidence) => <WorkflowEvidence evidence={evidence} key={evidence.chunk_id} />) : <p className="text-sm text-muted-foreground">No evidence references were returned.</p>}</div>
          </section>
          <section className="panel p-5"><div className="flex items-center gap-2"><Fingerprint aria-hidden className="size-5 text-brand" /><h2 className="font-heading text-lg font-semibold">Binding</h2></div><dl className="mt-4 space-y-3 text-xs"><div><dt className="text-muted-foreground">Payload hash</dt><dd className="mt-1 break-all font-mono">{record.payload_hash}</dd></div><div><dt className="text-muted-foreground">Evidence hash</dt><dd className="mt-1 break-all font-mono">{record.evidence_snapshot_hash}</dd></div><div><dt className="text-muted-foreground">Workflow run</dt><dd className="mt-1 break-all font-mono">{record.workflow_run_id}</dd></div></dl></section>
        </aside>
      </div>

      <Modal
        description="Rejection is audited and cannot create a workflow task."
        footer={<><Button disabled={reject.isPending} onClick={() => setRejectOpen(false)} variant="secondary">Cancel</Button><Button form="reject-proposal-form" isLoading={reject.isPending} type="submit" variant="danger">Reject proposal</Button></>}
        onClose={() => setRejectOpen(false)}
        open={rejectOpen}
        title="Reject this proposal?"
      >
        <form id="reject-proposal-form" onSubmit={rejectionForm.handleSubmit((values) => reject.mutate(values))}>
          <label className="text-sm font-semibold" htmlFor="rejection-comment">Review comment</label>
          <textarea className="mt-2 min-h-28 w-full rounded-md border border-border bg-surface px-3 py-2" id="rejection-comment" {...rejectionForm.register("comment")} />
          {rejectionForm.formState.errors.comment ? <p className="mt-1 text-sm text-danger" role="alert">{rejectionForm.formState.errors.comment.message}</p> : null}
        </form>
      </Modal>

      <Modal
        description="Editing invalidates this version and creates a new pending proposal. It does not create a task."
        footer={<><Button disabled={edit.isPending} onClick={() => setEditOpen(false)} variant="secondary">Cancel</Button><Button form="edit-proposal-form" isLoading={edit.isPending} type="submit">Create revised proposal</Button></>}
        onClose={() => setEditOpen(false)}
        open={editOpen}
        title="Edit into a new proposal version"
      >
        <form className="grid gap-4 sm:grid-cols-2" id="edit-proposal-form" onSubmit={editForm.handleSubmit((values) => edit.mutate(values))}>
          <div className="sm:col-span-2"><label className="text-sm font-semibold" htmlFor="edit-title">Title</label><input className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="edit-title" {...editForm.register("title")} />{editForm.formState.errors.title ? <p className="mt-1 text-sm text-danger" role="alert">{editForm.formState.errors.title.message}</p> : null}</div>
          <div className="sm:col-span-2"><label className="text-sm font-semibold" htmlFor="edit-description">Description</label><textarea className="mt-2 min-h-28 w-full rounded-md border border-border bg-surface px-3 py-2" id="edit-description" {...editForm.register("description")} />{editForm.formState.errors.description ? <p className="mt-1 text-sm text-danger" role="alert">{editForm.formState.errors.description.message}</p> : null}</div>
          <div><label className="text-sm font-semibold" htmlFor="edit-assignee">Assignee</label><input className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="edit-assignee" {...editForm.register("assignee")} /><p className="mt-1 text-xs text-muted-foreground">Blank retains the current value.</p></div>
          <div><label className="text-sm font-semibold" htmlFor="edit-priority">Priority</label><select className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="edit-priority" {...editForm.register("priority")}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></div>
          <div><label className="text-sm font-semibold" htmlFor="edit-due">Due date and time</label><input className="mt-2 min-h-11 w-full rounded-md border border-border bg-surface px-3" id="edit-due" type="datetime-local" {...editForm.register("due_at")} /><p className="mt-1 text-xs text-muted-foreground">Blank retains the current value.</p></div>
          <div className="sm:col-span-2"><label className="text-sm font-semibold" htmlFor="edit-reasoning">Reasoning summary</label><textarea className="mt-2 min-h-24 w-full rounded-md border border-border bg-surface px-3 py-2" id="edit-reasoning" {...editForm.register("reasoning_summary")} /></div>
          <div className="sm:col-span-2"><label className="text-sm font-semibold" htmlFor="edit-comment">Review comment (optional)</label><textarea className="mt-2 min-h-20 w-full rounded-md border border-border bg-surface px-3 py-2" id="edit-comment" {...editForm.register("comment")} /></div>
        </form>
      </Modal>
    </div>
  );
}
