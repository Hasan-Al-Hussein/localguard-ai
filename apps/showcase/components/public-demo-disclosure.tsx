import { FlaskConical } from "lucide-react";

export function PublicDemoDisclosure() {
  return (
    <aside
      aria-label="Public demo disclosure"
      className="public-demo-disclosure"
      data-public-demo-disclosure
    >
      <FlaskConical aria-hidden className="size-3.5" />
      <span>
        Public portfolio demo with synthetic data. No uploads, persistence, live
        AI, or real-world actions.
      </span>
    </aside>
  );
}
