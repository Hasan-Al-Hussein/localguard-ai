"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { AuthProvider } from "./auth-provider";
import { NoticeProvider } from "./notice-provider";

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15_000,
            retry: (failureCount, error) => {
              const status = typeof error === "object" && error && "status" in error ? Number(error.status) : 0;
              return status >= 400 && status < 500 ? false : failureCount < 2;
            },
            refetchOnWindowFocus: false,
          },
          mutations: { retry: false },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <NoticeProvider>
        <AuthProvider>{children}</AuthProvider>
      </NoticeProvider>
    </QueryClientProvider>
  );
}
