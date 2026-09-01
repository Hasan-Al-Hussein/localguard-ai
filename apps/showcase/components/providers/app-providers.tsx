"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { NoticeProvider } from "@/components/providers/notice-provider";
import { AuthProvider } from "./auth-provider";

export function AppProviders({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            refetchOnWindowFocus: false,
            retry: false,
            staleTime: Number.POSITIVE_INFINITY,
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
