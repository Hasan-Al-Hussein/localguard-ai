"use client";

import { ErrorState } from "@/components/ui/async-state";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <main className="mx-auto grid min-h-dvh max-w-3xl place-items-center p-6" id="main-content">
      <ErrorState error={error} onRetry={reset} />
    </main>
  );
}
