"use client";

import { LockKeyhole, RefreshCw } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, type ReactNode } from "react";
import { useAuth } from "@/components/providers/auth-provider";
import { Button } from "@/components/ui/button";
import { PageSkeleton } from "@/components/ui/async-state";

export function AuthGuard({ children }: { children: ReactNode }) {
  const { user, isLoading, error } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (!isLoading && !error && !user) router.replace("/login");
  }, [error, isLoading, router, user]);

  if (isLoading) {
    return <div className="mx-auto max-w-7xl p-6"><PageSkeleton /></div>;
  }

  if (error) {
    return (
      <main className="grid min-h-dvh place-items-center p-6" id="main-content">
        <section className="panel max-w-lg p-7 text-center" role="alert">
          <span className="mx-auto grid size-12 place-items-center rounded-xl bg-danger-soft text-danger">
            <LockKeyhole aria-hidden className="size-6" />
          </span>
          <h1 className="mt-4 font-heading text-xl font-semibold">Local services are unavailable</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            Start LocalGuard’s local stack, then retry. Your browser has not sent credentials or documents anywhere else.
          </p>
          <Button className="mt-5" icon={<RefreshCw aria-hidden className="size-4" />} onClick={() => window.location.reload()}>
            Retry connection
          </Button>
        </section>
      </main>
    );
  }

  if (!user) return null;
  return children;
}
