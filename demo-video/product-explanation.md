# LocalGuard AI product explanation

## The problem

Operations and compliance teams often need to turn long policies into time-sensitive work. A rule
may be buried in a PDF, its exact source may be lost when somebody summarizes it, and an
unverified answer can too easily become an action.

## What LocalGuard AI does

LocalGuard AI is a local-first evidence workspace. It indexes PDF, DOCX, and TXT documents,
answers questions only when the retrieved evidence is sufficient, and links every answer to an
exact stored passage. When the request would create work, LocalGuard prepares an inert proposal
and waits for an authenticated reviewer. Approval creates one internal workflow task; it does not
perform an external business action.

## Concrete example

The demonstration uses an original synthetic vendor-access policy. The policy says:

> The Service Desk must disable the vendor account within one hour after receiving the
> offboarding notice.

A reviewer asks how long the Service Desk has. LocalGuard returns “within one hour” and opens the
exact highlighted passage on PDF page 2. For a clearly labeled synthetic September 1 scenario,
the reviewer records a 09:00 UTC notice and asks for the required account-disable task. LocalGuard derives a high-priority
proposal assigned to the Service Desk and due at 10:00 UTC. No task exists before approval. After
the reviewer approves the exact proposal and evidence snapshot, exactly one LocalGuard task is
created and the complete causal chain is visible in the audit log.

## High-level pipeline

1. A user uploads a bounded PDF, DOCX, or TXT document.
2. LocalGuard validates it, preserves an immutable revision, extracts source-aware text, and
   stores local embeddings and searchable chunks.
3. A question is sent through the Next.js interface to FastAPI.
4. PostgreSQL full-text search and pgvector retrieve candidate evidence.
5. A sufficiency gate rejects unsupported questions before generation.
6. The local Ollama model confirms a bounded evidence binding; application code validates the
   response and resolves exact citations.
7. Answers return with clickable source proof.
8. Action requests enter a LangGraph workflow that creates only an inert proposal.
9. An authenticated reviewer approves, edits, or rejects the exact proposal version.
10. PostgreSQL uniqueness permits one task, while the audit trail records the request, evidence,
    decision, and outcome.

## Plain-language demo checklist

- **User:** an operations or compliance reviewer.
- **Pain:** a policy rule can be buried, detached from its proof, or acted on too early.
- **Input:** indexed PDF, DOCX, or TXT evidence plus a question or proposed action.
- **Process:** retrieve evidence, check sufficiency, validate the local model response, and bind
  the result to exact stored source locations.
- **Answer output:** a grounded answer with clickable proof.
- **Action output:** an inert, evidence-bound proposal waiting for human review.
- **Approved result:** exactly one internal LocalGuard task plus an audit chain.
- **Value:** faster review without hiding the source or bypassing the human decision.

## Honest scope

LocalGuard AI is a single-machine engineering demonstration, not legal advice or a production
multi-tenant compliance platform. Models run locally with no configured cloud-model fallback,
but bootstrap downloads the pinned model files. Citations make answers inspectable; they do not
make every possible answer automatically correct. The measured 25/25 result applies only to the
versioned synthetic evaluation corpus.
