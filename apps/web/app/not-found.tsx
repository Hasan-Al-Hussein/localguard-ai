import { SearchX } from "lucide-react";
import { Link } from "@/components/ui/app-link";
import { EmptyState } from "@/components/ui/async-state";

export default function NotFound() {
  return (
    <main className="mx-auto grid min-h-dvh max-w-3xl place-items-center p-6" id="main-content">
      <EmptyState
        action={<Link className="inline-flex min-h-11 items-center justify-center rounded-md border border-brand bg-brand px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-hover" href="/overview">Return to overview</Link>}
        description="The link may be outdated, or this record may no longer be available."
        icon={<SearchX aria-hidden className="size-6" />}
        title="Page not found"
      />
    </main>
  );
}
