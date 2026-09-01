import { SearchX } from "lucide-react";
import { ProofGateMark } from "@/components/brand/proof-gate-mark";
import { Link } from "@/components/ui/app-link";
import { PublicDemoDisclosure } from "../components/public-demo-disclosure";

export default function NotFound() {
  return (
    <div className="public-demo-frame">
      <PublicDemoDisclosure />
      <main className="showcase-not-found" id="main-content">
        <section>
          <span className="proof-brand-tile showcase-brand-mark">
            <ProofGateMark className="size-8" />
          </span>
          <SearchX aria-hidden className="showcase-not-found-icon" />
          <p>404 · Evidence route unavailable</p>
          <h1>Page not found</h1>
          <span>
            This static portfolio demo only publishes the fixed, synthetic
            walkthrough routes.
          </span>
          <Link className="showcase-primary-action" href="/overview">
            Return to the workspace
          </Link>
        </section>
      </main>
    </div>
  );
}
