# LocalGuard AI shot list

## Screenshot set — capture before video

All screenshots use a 1440×1000 viewport, one device pixel per CSS pixel, disabled screenshot
animations, loaded fonts, and an intentionally blurred active element so the skip link never
appears accidentally.

| Step | Filename | Route/state | Proof to keep visible |
|---|---|---|---|
| 1 | `step-01-sign-in-local-workspace.png` | `/login`, empty fields | Local-only positioning; no password. |
| 2 | `step-02-overview-system-status.png` | `/overview` | Cinematic evidence pipeline and live local status. |
| 3 | `step-03-inspect-indexed-document.png` | `/documents`, vendor filter | Ready synthetic vendor policy. |
| 4 | `step-04-ask-evidence-question.png` | `/ask`, question entered | Exact canonical question before submission. |
| 5 | `step-05-submit-grounded-question.png` | queued/retrieving state | Honest evidence-checking state. |
| 6 | `step-06-grounded-answer-with-citation.png` | succeeded answer | One-hour answer and source chip. |
| 7 | `step-07-open-exact-source-proof.png` | cited document route | Page 2 highlighted source sentence. |
| 8 | `step-08-propose-evidence-bound-action.png` | action request entered | Trusted 09:00 UTC event and review instruction. |
| 9 | `step-09-review-pending-proposal.png` | pending approval | “Nothing has been created yet,” exact evidence and proposal. |
| 10 | `step-10-approved-task-created-once.png` | task detail | One task, approval provenance, Service Desk/high/10:00 UTC. |
| 11 | `step-11-inspect-causal-audit-trail.png` | workflow audit | Request → proposal → decision → task chain. |
| 12 | `step-12-verify-evaluation-results.png` | evaluation detail | Ollama identity, 25/25, passing gates. |

## Real browser recording

- Resolution: 1920×1080.
- Authentication is completed in an unrecorded browser context; the recording begins at Overview.
- Journey: Overview → Documents → Ask → exact citation → Propose action → pending approval →
  approve once → task → audit → evaluation.
- Semantic locators are used instead of coordinates.
- The private staging copy stays under ignored `demo-video/recording/output/`. The verified,
  credential-free source recording used by Remotion is tracked at
  `demo-video/remotion/public/recordings/source-product-flow.webm` with a timestamp manifest.
- The recording never displays `.env`, credentials, cookies, raw model responses, or local
  filesystem paths.

## Verification frames

Inspect at minimum the final render near 00:08, 00:24, 00:38, 00:50, 01:00, 01:10, 01:20,
01:36, 01:56, 02:05, 02:22, and 02:36. Reject black frames, frozen transitions, clipped captions, unreadable
product text, cursor obstruction, or a state that contradicts the narration.
