# LocalGuard AI product-demo script

Target: 160 seconds, 1920×1080, 30 fps.

## Narration

### 00:00–00:16: The problem

Operations reviewers turn long policies into time-sensitive work. Searching by hand can hide
the rule, lose its source, or trigger action from an unverified answer.

### 00:16–00:32: The solution

LocalGuard AI is a private evidence workspace running on one computer. It answers from indexed
files, opens exact proof, and keeps actions behind human review.

### 00:32–00:44: The example

Imagine vendor offboarding. A synthetic policy requires the Service Desk to disable an account
within one hour of notice.

### 00:44–00:56: Step one: input

Step one: open Documents. LocalGuard indexes the PDF pages locally and preserves an immutable
revision.

### 00:56–01:24: Step two: answer with proof

Step two: ask, “How long does the Service Desk have?” LocalGuard searches the indexed evidence,
checks whether it is sufficient, and returns “within one hour.” The source button opens page two
and highlights the exact stored sentence, making the answer inspectable instead of merely
plausible.

### 01:24–01:50: Step three: propose an action

Step three: choose Propose an action. In a synthetic September first scenario, the notice arrives
at nine A.M. U.T.C. LocalGuard derives a high-priority Service Desk proposal due at ten, but
creates no task yet.

### 01:50–02:12: Result and value

The reviewer checks the proposal and evidence, then approves it. Only then does one workflow task
appear. Its owner, priority, deadline, and source stay visible. The audit log records the decision
and task creation.

### 02:12–02:32: Technical pipeline

Next.js calls FastAPI. PostgreSQL and pgvector retrieve evidence. A Celery worker checks it with
Ollama. LangGraph pauses actions for human approval, and PostgreSQL permits one task.

### 02:32–02:40: Close

LocalGuard: source-backed answers and reviewable work, with evidence before action.

## On-screen copy

- Problem: `The rule is buried. The source is lost. The action is risky.`
- Solution: `Local evidence → exact proof → human gate → one task`
- Example: `Vendor offboarding · notice received 09:00 UTC`
- Result: `Service Desk · High priority · Due 10:00 UTC`
- Close: `Evidence before action.`

## Recording inputs

Evidence question:

> How long does the Service Desk have to disable a vendor account after it receives an
> offboarding notice?

Action request:

> For a synthetic September 1 scenario, an authorized sponsor's vendor offboarding notice was
> received at 2026-09-01T09:00:00Z. Propose the required account-disable task; do not execute it
> without review.
