"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import {
  QuestionJobSchema,
  QuestionRequestSchema,
  FindingsResponseSchema,
  ProposalsResponseSchema,
  WorkflowRunSchema,
  WorkflowStartAcceptedSchema,
  type QuestionJob,
  type QuestionRequest,
  type Finding,
  type WorkflowRun,
} from "@localguard/contracts";
import { useMutation, useQuery } from "@tanstack/react-query";
import { BookOpenCheck, Bot, ChevronDown, ClipboardCheck, Database, FileSearch, Link2, Send, ShieldAlert, UserCheck, UserRound } from "lucide-react";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import Image from "next/image";
import { Link } from "@/components/ui/app-link";
import { useState } from "react";
import { useForm, useWatch } from "react-hook-form";
import { AnswerCitationEvidence, AnswerCitationLink } from "@/components/evidence/citation-link";
import { FindingCard } from "@/components/findings/finding-card";
import { useAuth } from "@/components/providers/auth-provider";
import { InlineBanner } from "@/components/ui/async-state";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/ui/page-header";
import { StatusBadge } from "@/components/ui/status-badge";
import { apiRequest, errorMessage } from "@/lib/api-client";
import { cn } from "@/lib/cn";
import { formatDuration } from "@/lib/format";
import { cascadeVariants, revealVariants, stateTransition } from "@/lib/motion";
import { queryKeys } from "@/lib/query-keys";

type ConversationItem =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; job: QuestionJob };

type IdempotentSubmission = {
  request: QuestionRequest;
  idempotencyKey: string;
};

const starters = [
  "How quickly must the Service Desk disable a departing vendor account?",
  "Who owns the approved vendor offboarding action?",
  "Can LocalGuard authorize an action without supporting evidence?",
];

const actionStarters = [
  "Create a task for the most urgent deadline in the indexed evidence.",
  "Propose an action item for the responsible party in the incident procedure.",
  "Create a task to address the highest-severity documented risk.",
];

const trustCues = [
  { icon: Database, label: "Indexed evidence only" },
  { icon: Link2, label: "Clickable source proof" },
  { icon: UserCheck, label: "Human approval for actions" },
];

function WorkflowModeSelector({
  embedded = false,
  mode,
  onChange,
}: {
  embedded?: boolean;
  mode: "question" | "action";
  onChange: (mode: "question" | "action") => void;
}) {
  const reduceMotion = useReducedMotion();
  return (
    <fieldset className={cn("ask-mode-rail grid gap-2 p-2 sm:grid-cols-2", !embedded && "panel")}>
      <legend className="sr-only">Choose an evidence workflow</legend>
      <motion.label className={cn("mode-option flex min-h-12 cursor-pointer items-center rounded-xl border px-4 py-3 text-sm font-semibold", mode === "question" ? "border-brand bg-brand text-white shadow-[0_8px_20px_rgb(18_63_97/0.18)]" : "border-transparent bg-surface-raised text-muted-foreground hover:text-foreground")} layout transition={stateTransition()} whileTap={reduceMotion ? undefined : { scale: 0.985 }}><input className="sr-only" name="workflow-mode" onChange={() => onChange("question")} type="radio" checked={mode === "question"} /><BookOpenCheck aria-hidden className="mr-2 size-4" />Evidence answer</motion.label>
      <motion.label className={cn("mode-option flex min-h-12 cursor-pointer items-center rounded-xl border px-4 py-3 text-sm font-semibold", mode === "action" ? "border-pending/40 bg-pending-soft text-pending shadow-[0_8px_20px_rgb(146_64_14/0.12)]" : "border-transparent bg-surface-raised text-muted-foreground hover:text-foreground")} layout transition={stateTransition()} whileTap={reduceMotion ? undefined : { scale: 0.985 }}><input className="sr-only" name="workflow-mode" onChange={() => onChange("action")} type="radio" checked={mode === "action"} /><ClipboardCheck aria-hidden className="mr-2 size-4" />Propose an action</motion.label>
    </fieldset>
  );
}

function AnswerText({ text }: { text: string }) {
  return <div className="space-y-3 text-[0.98rem] leading-7">{text.split(/\n{2,}/).filter(Boolean).map((paragraph, index) => <p key={`${index}-${paragraph.slice(0, 20)}`}>{paragraph}</p>)}</div>;
}

function AnswerCard({ job }: { job: QuestionJob }) {
  if (job.state === "failed") {
    return <InlineBanner title="The question job failed" tone="danger">{job.error_detail ?? job.error_code ?? "The local API did not provide a failure detail."}</InlineBanner>;
  }
  const answer = job.answer;
  if (!answer) return <InlineBanner title="No answer was returned" tone="danger">The completed job did not include an answer record.</InlineBanner>;

  return (
    <article className="panel answer-card overflow-hidden">
      <header className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-muted/70 px-5 py-3.5 sm:px-6">
        <span className="brand-mark grid size-9 place-items-center rounded-xl text-white"><Bot aria-hidden className="size-4" /></span>
        <p className="font-heading text-sm font-semibold">LocalGuard</p>
        <StatusBadge className="ml-auto" status={answer.insufficient_evidence ? "insufficient" : answer.citations.length ? "cited" : "completed"} />
      </header>
      <div className="answer-evidence-stack space-y-4 p-5 sm:p-6">
        {answer.insufficient_evidence ? <InlineBanner title="The indexed evidence is not sufficient" tone="pending">LocalGuard did not find enough support to answer safely. Try narrowing the question or add a relevant document.</InlineBanner> : null}
        <section aria-label="Evidence answer" className="answer-primary"><AnswerText text={answer.text} /></section>

        {answer.citations.length ? (
          <section aria-labelledby={`sources-${job.id}`} className="answer-source-proof rounded-xl border border-evidence/20 bg-evidence-soft/30 p-4">
            <h3 className="text-xs font-bold tracking-[0.12em] text-muted-foreground uppercase" id={`sources-${job.id}`}>Sources</h3>
            <p className="mt-1 text-xs text-muted-foreground">Open the exact stored passage behind this answer.</p>
            <div className="mt-2.5 flex flex-wrap gap-2">{answer.citations.map((citation) => <AnswerCitationLink citation={citation} key={citation.id} />)}</div>
          </section>
        ) : null}

        <details className="group overflow-hidden rounded-xl border border-border bg-surface-muted transition-colors open:bg-surface-raised">
          <summary className="flex min-h-11 cursor-pointer list-none items-center gap-2 px-4 py-2 text-sm font-semibold">
            <FileSearch aria-hidden className="size-4 text-brand" />Answer details
            <span className="ml-auto text-xs font-normal text-muted-foreground">Retrieval {formatDuration(answer.retrieval_ms)} · generation {formatDuration(answer.generation_ms)}</span>
            <ChevronDown aria-hidden className="size-4 transition-transform group-open:rotate-180" />
          </summary>
          <div className="space-y-4 border-t border-border p-4">
            <dl className="grid gap-3 text-xs sm:grid-cols-2"><div><dt className="text-muted-foreground">Model</dt><dd className="mt-1 font-mono">{answer.model_name}</dd></div><div><dt className="text-muted-foreground">Prompt version</dt><dd className="mt-1 font-mono">{answer.prompt_version}</dd></div></dl>
            {answer.citations.map((citation) => <AnswerCitationEvidence citation={citation} key={citation.id} />)}
          </div>
        </details>
        <p className="font-mono text-[0.68rem] text-muted-foreground">Question job: {job.id}</p>
      </div>
    </article>
  );
}

function WorkflowCard({
  run,
  proposalId,
  findings,
  canReview,
}: {
  run: WorkflowRun;
  proposalId?: string;
  findings: Finding[];
  canReview: boolean;
}) {
  const waiting = run.state === "waiting_approval";
  const failed = run.state === "failed";
  return (
    <article className="panel answer-card overflow-hidden">
      <header className="flex flex-wrap items-center gap-2 border-b border-border bg-surface-muted/70 px-5 py-3.5 sm:px-6">
        <span className="brand-mark grid size-9 place-items-center rounded-xl text-white"><Bot aria-hidden className="size-4" /></span>
        <p className="font-heading text-sm font-semibold">Action analysis</p>
        <StatusBadge className="ml-auto" status={run.state} />
      </header>
      <div className="space-y-4 p-5 sm:p-6">
        {waiting ? <InlineBanner title="Human approval is required" tone="pending">The workflow produced a proposal, not a task. No task exists until a reviewer approves the bound proposal.</InlineBanner> : null}
        {run.insufficient_evidence ? <InlineBanner title="The indexed evidence is not sufficient" tone="pending">No proposal or task was created because the action could not be grounded safely.</InlineBanner> : null}
        {failed ? <InlineBanner title="The workflow failed" tone="danger">{run.error_detail ?? run.error_code ?? "The local workflow did not return a failure detail."}</InlineBanner> : null}
        {run.answer_text ? <AnswerText text={run.answer_text} /> : null}
        {findings.length ? (
          <section aria-labelledby={`findings-${run.id}`}>
            <h3 className="text-xs font-bold tracking-[0.12em] text-muted-foreground uppercase" id={`findings-${run.id}`}>Structured findings</h3>
            <div className="mt-3 space-y-4">{findings.map((finding) => <FindingCard finding={finding} key={finding.id} />)}</div>
          </section>
        ) : null}
        {waiting ? (
          <div className="flex flex-wrap items-center gap-3 border-t border-border pt-4">
            <ClipboardCheck aria-hidden className="size-5 text-pending" />
            <p className="min-w-0 flex-1 text-sm text-muted-foreground">{canReview ? "Review the immutable proposal binding before deciding." : "A reviewer or administrator must decide this proposal."}</p>
            {canReview ? <Link className="button-base button-primary inline-flex min-h-11 items-center border px-4 text-sm font-semibold" href={proposalId ? `/approvals/${encodeURIComponent(proposalId)}` : "/approvals"}>{proposalId ? "Review proposal" : "Open approval queue"}</Link> : null}
          </div>
        ) : null}
        <p className="break-all font-mono text-[0.68rem] text-muted-foreground">Workflow run: {run.id}</p>
      </div>
    </article>
  );
}

export function AskScreen() {
  const [mode, setMode] = useState<"question" | "action">("question");
  const [conversation, setConversation] = useState<ConversationItem[]>([]);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [workflowId, setWorkflowId] = useState<string | null>(null);
  const [requestError, setRequestError] = useState<string | null>(null);
  const reduceMotion = useReducedMotion();
  const { user } = useAuth();
  const canReview = user?.role === "reviewer" || user?.role === "admin";
  const { register, handleSubmit, setValue, reset, control, formState: { errors } } = useForm<QuestionRequest>({
    resolver: zodResolver(QuestionRequestSchema),
    defaultValues: { question: "", document_ids: [] },
  });
  const questionText = useWatch({ control, name: "question" }) ?? "";

  const createQuestion = useMutation({
    mutationFn: ({ request, idempotencyKey }: IdempotentSubmission) => apiRequest("/questions", QuestionJobSchema, { method: "POST", body: JSON.stringify(request), headers: { "Idempotency-Key": idempotencyKey } }),
    onSuccess: (job) => {
      if (job.state === "succeeded" || job.state === "failed") setConversation((items) => [...items, { id: job.id, role: "assistant", job }]);
      else setPendingId(job.id);
    },
    onError: (error) => setRequestError(errorMessage(error)),
  });

  const createWorkflow = useMutation({
    mutationFn: ({ request, idempotencyKey }: IdempotentSubmission) => apiRequest("/workflow-runs", WorkflowStartAcceptedSchema, { method: "POST", body: JSON.stringify(request), headers: { "Idempotency-Key": idempotencyKey } }),
    onSuccess: (accepted) => setWorkflowId(accepted.run.id),
    onError: (error) => setRequestError(errorMessage(error)),
  });

  const pendingQuestion = useQuery({
    queryKey: pendingId ? queryKeys.question(pendingId) : ["question", "none"],
    queryFn: () => apiRequest(`/questions/${encodeURIComponent(pendingId ?? "")}`, QuestionJobSchema),
    enabled: Boolean(pendingId),
    refetchInterval: (query) => ["succeeded", "failed"].includes(query.state.data?.state ?? "") ? false : 1_000,
  });

  const workflow = useQuery({
    queryKey: workflowId ? queryKeys.workflow(workflowId) : ["workflow", "none"],
    queryFn: () => apiRequest(`/workflow-runs/${encodeURIComponent(workflowId ?? "")}`, WorkflowRunSchema),
    enabled: Boolean(workflowId),
    refetchInterval: (query) => query.state.data?.state === "running" ? 1_000 : false,
  });

  const findings = useQuery({
    queryKey: ["findings", workflowId ?? "none"],
    queryFn: () => apiRequest(`/findings?workflow_run_id=${encodeURIComponent(workflowId ?? "")}&limit=100`, FindingsResponseSchema),
    enabled: Boolean(workflowId && workflow.data && workflow.data.state !== "running"),
  });

  const proposals = useQuery({
    queryKey: ["approvals", "workflow", workflowId ?? "none"],
    queryFn: () => apiRequest("/approvals?offset=0&limit=100", ProposalsResponseSchema),
    enabled: Boolean(canReview && workflowId && workflow.data?.state === "waiting_approval"),
  });

  function submit(values: QuestionRequest) {
    setRequestError(null);
    if (mode === "action") {
      setWorkflowId(null);
      reset();
      createWorkflow.mutate({ request: values, idempotencyKey: crypto.randomUUID() });
      return;
    }
    const completedPending = pendingQuestion.data && ["succeeded", "failed"].includes(pendingQuestion.data.state) ? pendingQuestion.data : null;
    setConversation((items) => [
      ...items,
      ...(completedPending && !items.some((item) => item.id === completedPending.id) ? [{ id: completedPending.id, role: "assistant" as const, job: completedPending }] : []),
      { id: crypto.randomUUID(), role: "user", text: values.question },
    ]);
    setPendingId(null);
    reset();
    createQuestion.mutate({ request: values, idempotencyKey: crypto.randomUUID() });
  }

  const pendingTerminal = pendingQuestion.data && ["succeeded", "failed"].includes(pendingQuestion.data.state);
  const workflowRecord = workflow.data ?? createWorkflow.data?.run;
  const proposal = proposals.data?.items.find((item) => item.workflow_run_id === workflowId);
  const isWorking = createQuestion.isPending || createWorkflow.isPending || Boolean(pendingId && !pendingTerminal && !pendingQuestion.isError) || Boolean(workflowId && workflowRecord?.state === "running" && !workflow.isError);
  const isEmptyWorkbench = conversation.length === 0 && !workflowRecord;
  const composer = (
    <form className={cn("ask-composer-form composer-panel p-3", isEmptyWorkbench ? "ask-composer-embedded" : "ask-composer panel")} onSubmit={handleSubmit(submit)}>
      <label className="sr-only" htmlFor="question">{mode === "question" ? "Ask a question about indexed documents" : "Describe an action to ground in indexed documents"}</label>
      <textarea aria-describedby="question-help" className="min-h-24 w-full resize-y rounded-xl border border-transparent bg-surface-raised px-4 py-3 text-base leading-6 placeholder:text-slate-400 focus:border-evidence/30 focus:bg-white" disabled={isWorking} id="question" maxLength={4000} placeholder={mode === "question" ? "Ask about an obligation, deadline, risk, or required action…" : "Create a task for an evidence-backed deadline or obligation…"} {...register("question")} />
      <div className="mt-2 flex items-center gap-3 px-1"><p className={cn("text-xs text-muted-foreground", errors.question && "text-danger")} id="question-help" role={errors.question ? "alert" : undefined}>{errors.question?.message ?? `${questionText.length.toLocaleString()} / 4,000 characters`}</p><Button aria-busy={isWorking} className="ml-auto" disabled={isWorking} icon={<Send aria-hidden className="size-4" />} type="submit">{mode === "question" ? "Ask" : "Analyze action"}</Button></div>
    </form>
  );
  return (
    <motion.div animate="visible" className="ask-screen mx-auto max-w-6xl space-y-5" initial={reduceMotion ? false : "hidden"} variants={cascadeVariants}>
      <motion.div className="ask-page-header" variants={revealVariants}><PageHeader description="Ask questions across indexed documents. Answers are constrained to retrieved evidence and link to stable stored anchors." eyebrow="Evidence workbench" title="Ask LocalGuard" /></motion.div>

      <motion.section className={cn("ask-query-surface", isEmptyWorkbench ? "ask-workbench panel overflow-hidden" : "ask-query-surface--active space-y-3")} variants={revealVariants}>
        <WorkflowModeSelector embedded={isEmptyWorkbench} mode={mode} onChange={setMode} />
        {composer}
        <AnimatePresence initial={false}>
          {isEmptyWorkbench ? (
            <motion.div animate={{ opacity: 1, y: 0 }} className="ask-hero ask-hero--compact relative overflow-hidden p-5 sm:p-6 lg:p-7" exit={reduceMotion ? undefined : { opacity: 0, y: -8 }} initial={reduceMotion ? false : { opacity: 0, y: 8 }} key="ask-onboarding" transition={stateTransition()}>
              <div className="ask-hero-grid ask-hero-grid--compact">
                <AnimatePresence initial={false} mode="wait">
                  <motion.div
                    animate={{ opacity: 1, y: 0 }}
                    className="ask-hero-copy"
                    exit={reduceMotion ? undefined : { opacity: 0, y: -4 }}
                    initial={reduceMotion ? false : { opacity: 0, y: 6 }}
                    key={mode}
                    transition={stateTransition()}
                  >
                    <div className="flex items-center gap-3">
                      <span className="relative grid size-10 place-items-center rounded-xl bg-evidence-soft text-evidence shadow-[inset_0_1px_0_rgb(255_255_255/0.8)]">{mode === "question" ? <BookOpenCheck aria-hidden className="size-5" /> : <ClipboardCheck aria-hidden className="size-5" />}</span>
                      <p className="ask-hero-kicker mt-0">Private evidence workbench</p>
                    </div>
                    <h2 className="mt-4 max-w-2xl font-heading text-2xl font-semibold tracking-[-0.04em]">{mode === "question" ? "Ask the document. Inspect the proof." : "Turn proven evidence into reviewable work."}</h2>
                    <p className="mt-2 max-w-2xl text-sm leading-6 text-muted-foreground">{mode === "question" ? "Get an answer constrained to indexed evidence, then open the exact stored passage." : "Bind a proposal to one source rule. It stays inert until an authorized reviewer decides."}</p>
                    <ol aria-label="LocalGuard safeguards" className="evidence-journey evidence-journey--compact mt-4 flex flex-wrap gap-2">
                      {trustCues.map(({ icon: Icon, label }) => (
                        <li className="evidence-stage relative flex min-h-10 items-center gap-2 rounded-lg border border-white/15 bg-white/5 px-3 py-2 text-xs font-semibold text-muted-foreground" key={label}>
                          <Icon aria-hidden className="size-3.5 shrink-0 text-evidence" />
                          <span>{label}</span>
                        </li>
                      ))}
                    </ol>
                  </motion.div>
                </AnimatePresence>
                <div aria-hidden className="ask-vault-visual ask-vault-visual--compact hidden sm:block">
                  <Image alt="" fill priority sizes="(max-width: 767px) 0px, 34vw" src="/brand/evidence-vault-hero.png" />
                  <span className="ask-vault-badge ask-vault-badge-source">SOURCE / LOCAL</span>
                  <span className="ask-vault-badge ask-vault-badge-proof">PROOF / EXACT</span>
                  <span className="ask-vault-badge ask-vault-badge-gate">GATE / HUMAN</span>
                </div>
              </div>
              <AnimatePresence initial={false} mode="wait">
                <motion.div animate={{ opacity: 1, y: 0 }} aria-label="Suggested prompts" className="ask-prompt-grid relative mt-5 grid gap-2 sm:grid-cols-3" exit={reduceMotion ? undefined : { opacity: 0, y: 4 }} initial={reduceMotion ? false : { opacity: 0, y: 6 }} key={`${mode}-starters`} role="group" transition={stateTransition(0.03)}>
                  {(mode === "question" ? starters : actionStarters).map((starter) => <motion.button className="prompt-starter min-h-14 rounded-xl border border-border bg-surface-raised p-3 text-left text-sm font-semibold leading-5" key={starter} onClick={() => setValue("question", starter, { shouldValidate: true })} transition={stateTransition()} type="button" whileHover={reduceMotion ? undefined : { y: -2, scale: 1.005 }} whileTap={reduceMotion ? undefined : { scale: 0.985 }}>{starter}</motion.button>)}
                </motion.div>
              </AnimatePresence>
            </motion.div>
          ) : null}
        </AnimatePresence>
      </motion.section>
      <AnimatePresence initial={false}>
        {conversation.length ? (
          <motion.section aria-label="Conversation" className="ask-evidence-results space-y-4" layout>
            {conversation.map((item) => (
              <motion.div animate={{ opacity: 1, y: 0 }} initial={reduceMotion ? false : { opacity: 0, y: 12 }} key={item.id} layout="position" transition={stateTransition()}>
                {item.role === "user" ? <article className="ml-auto max-w-2xl rounded-2xl rounded-br-md bg-[linear-gradient(135deg,#174d73,#0e3655)] px-5 py-4 text-white shadow-[0_12px_26px_rgb(18_63_97/0.18)]"><div className="flex items-center gap-2 text-xs font-semibold text-slate-200"><UserRound aria-hidden className="size-4" />You</div><p className="mt-2 leading-7">{item.text}</p></article> : <AnswerCard job={item.job} />}
              </motion.div>
            ))}
            {pendingTerminal && pendingQuestion.data ? <motion.div animate={{ opacity: 1, y: 0 }} initial={reduceMotion ? false : { opacity: 0, y: 12 }} key={pendingQuestion.data.id} transition={stateTransition()}><AnswerCard job={pendingQuestion.data} /></motion.div> : null}
          </motion.section>
        ) : null}
      </AnimatePresence>
      <AnimatePresence initial={false}>
        {workflowRecord && workflowRecord.state !== "running" ? <motion.div animate={{ opacity: 1, y: 0 }} initial={reduceMotion ? false : { opacity: 0, y: 12 }} key={workflowRecord.id} transition={stateTransition()}><WorkflowCard canReview={canReview} findings={findings.data?.items ?? []} proposalId={proposal?.id} run={workflowRecord} /></motion.div> : null}
      </AnimatePresence>

      <AnimatePresence initial={false}>
        {isWorking ? <motion.div animate={{ opacity: 1, y: 0 }} aria-live="polite" className="evidence-progress panel flex items-center gap-3 p-4" exit={reduceMotion ? undefined : { opacity: 0, y: -6 }} initial={reduceMotion ? false : { opacity: 0, y: 8 }} key="evidence-progress" role="status" transition={stateTransition()}><span className="relative grid size-9 place-items-center rounded-xl bg-info-soft text-info"><Bot aria-hidden className="size-4" /><span className="absolute -right-0.5 -bottom-0.5 size-2.5 animate-pulse rounded-full bg-info ring-2 ring-surface" /></span><div className="min-w-0 flex-1"><p className="text-sm font-semibold">LocalGuard is checking the evidence</p><p className="text-xs text-muted-foreground">{workflowRecord?.state ?? pendingQuestion.data?.state ?? createQuestion.data?.state ?? (createWorkflow.isPending ? "submitting workflow" : "submitting")}…</p><span aria-hidden className="evidence-progress-line mt-2 block h-1 overflow-hidden rounded-full bg-brand-soft"><span className="block h-full w-1/3 rounded-full bg-evidence" /></span></div></motion.div> : null}
      </AnimatePresence>
      <AnimatePresence initial={false}>
        {requestError || pendingQuestion.isError || workflow.isError ? <motion.div animate={{ opacity: 1, y: 0 }} exit={reduceMotion ? undefined : { opacity: 0, y: -4 }} initial={reduceMotion ? false : { opacity: 0, y: 8 }} key="request-error" transition={stateTransition()}><InlineBanner title="The request could not be completed" tone="danger">{requestError ?? errorMessage(pendingQuestion.error ?? workflow.error)}</InlineBanner></motion.div> : null}
      </AnimatePresence>

      <p className="flex items-center gap-2 text-xs text-muted-foreground"><ShieldAlert aria-hidden className="size-4 text-pending" />Document text is untrusted. Action proposals remain inert until an authorized human decision passes the bound approval gate.</p>
    </motion.div>
  );
}
