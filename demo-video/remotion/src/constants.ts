export const FPS = 30;
export const WIDTH = 1920;
export const HEIGHT = 1080;

export const SCENE_DURATIONS = {
  problem: 480,
  solution: 480,
  example: 360,
  input: 360,
  answer: 840,
  proposal: 780,
  result: 660,
  pipeline: 600,
  close: 240,
} as const;

export const SCENE_STARTS = {
  problem: 0,
  solution: SCENE_DURATIONS.problem,
  example: SCENE_DURATIONS.problem + SCENE_DURATIONS.solution,
  input:
    SCENE_DURATIONS.problem +
    SCENE_DURATIONS.solution +
    SCENE_DURATIONS.example,
  answer:
    SCENE_DURATIONS.problem +
    SCENE_DURATIONS.solution +
    SCENE_DURATIONS.example +
    SCENE_DURATIONS.input,
  proposal:
    SCENE_DURATIONS.problem +
    SCENE_DURATIONS.solution +
    SCENE_DURATIONS.example +
    SCENE_DURATIONS.input +
    SCENE_DURATIONS.answer,
  result:
    SCENE_DURATIONS.problem +
    SCENE_DURATIONS.solution +
    SCENE_DURATIONS.example +
    SCENE_DURATIONS.input +
    SCENE_DURATIONS.answer +
    SCENE_DURATIONS.proposal,
  pipeline:
    SCENE_DURATIONS.problem +
    SCENE_DURATIONS.solution +
    SCENE_DURATIONS.example +
    SCENE_DURATIONS.input +
    SCENE_DURATIONS.answer +
    SCENE_DURATIONS.proposal +
    SCENE_DURATIONS.result,
  close:
    SCENE_DURATIONS.problem +
    SCENE_DURATIONS.solution +
    SCENE_DURATIONS.example +
    SCENE_DURATIONS.input +
    SCENE_DURATIONS.answer +
    SCENE_DURATIONS.proposal +
    SCENE_DURATIONS.result +
    SCENE_DURATIONS.pipeline,
} as const;

export const DURATION_IN_FRAMES = SCENE_STARTS.close + SCENE_DURATIONS.close;

export const COLORS = {
  obsidian: "#07121C",
  ink: "#0A3048",
  deepInk: "#06141F",
  mint: "#52E0C4",
  mintSoft: "#BDF8ED",
  blue: "#4F8CFF",
  amber: "#F2A93B",
  silver: "#DCE6E8",
  white: "#F7FBFC",
  muted: "#9FB1BA",
  danger: "#FF806C",
} as const;

export const SCREENSHOTS = {
  login: "screenshots/step-01-sign-in-local-workspace.png",
  overview: "screenshots/step-02-overview-system-status.png",
  document: "screenshots/step-03-inspect-indexed-document.png",
  question: "screenshots/step-04-ask-evidence-question.png",
  queued: "screenshots/step-05-submit-grounded-question.png",
  answer: "screenshots/step-06-grounded-answer-with-citation.png",
  citation: "screenshots/step-07-open-exact-source-proof.png",
  action: "screenshots/step-08-propose-evidence-bound-action.png",
  approval: "screenshots/step-09-review-pending-proposal.png",
  task: "screenshots/step-10-approved-task-created-once.png",
  audit: "screenshots/step-11-inspect-causal-audit-trail.png",
  evaluation: "screenshots/step-12-verify-evaluation-results.png",
} as const;

export type DemoProps = {
  showCaptions: boolean;
  narrationEnabled: boolean;
};
