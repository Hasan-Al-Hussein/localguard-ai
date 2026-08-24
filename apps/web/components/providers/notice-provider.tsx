"use client";

import { CheckCircle2, CircleAlert, X } from "lucide-react";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";

type Notice = { id: number; message: string; tone: "success" | "error" };
type NoticeContextValue = { notify: (message: string, tone?: Notice["tone"]) => void };

const NoticeContext = createContext<NoticeContextValue | null>(null);

export function NoticeProvider({ children }: { children: ReactNode }) {
  const [notice, setNotice] = useState<Notice | null>(null);

  const notify = useCallback((message: string, tone: Notice["tone"] = "success") => {
    setNotice({ id: Date.now(), message, tone });
  }, []);

  useEffect(() => {
    if (!notice) return;
    const timeout = window.setTimeout(() => setNotice(null), 4_500);
    return () => window.clearTimeout(timeout);
  }, [notice]);

  return (
    <NoticeContext.Provider value={{ notify }}>
      {children}
      {notice ? (
        <div
          aria-live="polite"
          className="fixed right-4 bottom-4 z-50 flex max-w-sm items-start gap-3 rounded-lg border border-border bg-surface p-4 text-sm shadow-xl"
          role="status"
        >
          {notice.tone === "success" ? (
            <CheckCircle2 aria-hidden className="mt-0.5 size-5 shrink-0 text-success" />
          ) : (
            <CircleAlert aria-hidden className="mt-0.5 size-5 shrink-0 text-danger" />
          )}
          <span className="pr-2">{notice.message}</span>
          <button
            aria-label="Dismiss notification"
            className="-m-2 ml-auto grid size-11 shrink-0 cursor-pointer place-items-center rounded-md text-muted-foreground hover:bg-surface-raised"
            onClick={() => setNotice(null)}
            type="button"
          >
            <X aria-hidden className="size-4" />
          </button>
        </div>
      ) : null}
    </NoticeContext.Provider>
  );
}

export function useNotice(): NoticeContextValue {
  const context = useContext(NoticeContext);
  if (!context) throw new Error("useNotice must be used inside NoticeProvider");
  return context;
}
