import {
  ArrowRight,
  BookOpenText,
  Fingerprint,
  ShieldCheck,
} from "lucide-react";
import { ProofGateMark } from "@/components/brand/proof-gate-mark";
import { ProofCoreScene } from "@/components/effects/proof-core-scene";
import { Link } from "@/components/ui/app-link";
import { PublicDemoDisclosure } from "./public-demo-disclosure";

const evidencePrinciples = [
  {
    icon: BookOpenText,
    label: "Source-bound answers",
    detail: "Every claim returns to an exact synthetic document anchor.",
  },
  {
    icon: Fingerprint,
    label: "Inspectable proof",
    detail: "Citations, audit records, and evaluation results stay traceable.",
  },
  {
    icon: ShieldCheck,
    label: "Human-gated action",
    detail: "Proposed work remains inert until a reviewer approves it.",
  },
] as const;

export function PublicShowcaseLanding() {
  return (
    <div className="public-demo-frame">
      <PublicDemoDisclosure />
      <main className="showcase-landing" id="main-content">
        <section
          className="showcase-landing-shell"
          aria-labelledby="showcase-title"
        >
          <div className="showcase-landing-copy">
            <div className="showcase-brand-lockup">
              <span className="proof-brand-tile showcase-brand-mark">
                <ProofGateMark className="size-8" />
              </span>
              <span>
                <strong>LocalGuard AI</strong>
                <small>Evidence before action</small>
              </span>
            </div>

            <p className="showcase-kicker">Interactive recruiter showcase</p>
            <h1 id="showcase-title">
              Inspect the proof.
              <span>Keep control of the action.</span>
            </h1>
            <p className="showcase-intro">
              Explore a deterministic LocalGuard workspace with synthetic policy
              documents, cited answers, reviewable workflow proposals, and a
              complete assurance trail.
            </p>

            <div className="showcase-actions">
              <Link className="showcase-primary-action" href="/overview">
                Enter the workspace{" "}
                <ArrowRight aria-hidden className="size-4" />
              </Link>
              <Link className="showcase-secondary-action" href="/documents">
                Browse evidence
              </Link>
            </div>

            <p className="showcase-safety-note">
              No account, upload, or external service is required. Refresh to
              reset the browser-memory walkthrough.
            </p>
          </div>

          <div
            className="showcase-visual"
            aria-label="LocalGuard evidence flow preview"
          >
            <ProofCoreScene priority />
            <div className="showcase-visual-caption">
              <span>
                <i /> Synthetic evidence plane
              </span>
              <strong>Reviewer ready</strong>
            </div>
          </div>
        </section>

        <section className="showcase-principles" aria-label="What to explore">
          {evidencePrinciples.map(({ icon: Icon, label, detail }, index) => (
            <article key={label}>
              <span className="showcase-principle-index">0{index + 1}</span>
              <Icon aria-hidden className="size-5" />
              <h2>{label}</h2>
              <p>{detail}</p>
            </article>
          ))}
        </section>
      </main>
    </div>
  );
}
