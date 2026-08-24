"use client";

import {
  AuthResponseSchema,
  CurrentUserResponseSchema,
  LoginRequestSchema,
  type LoginRequest,
  type User,
} from "@localguard/contracts";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createContext, useContext, type ReactNode } from "react";
import { z } from "zod";
import { ApiError, apiRequest, setCsrfToken } from "@/lib/api-client";
import { queryKeys } from "@/lib/query-keys";

type AuthContextValue = {
  user: User | null;
  isLoading: boolean;
  error: Error | null;
  login: (values: LoginRequest) => Promise<User>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const authQuery = useQuery({
    queryKey: queryKeys.auth,
    queryFn: () => apiRequest("/auth/me", CurrentUserResponseSchema),
    retry: false,
    staleTime: 30_000,
  });

  const loginMutation = useMutation({
    mutationFn: async (values: LoginRequest) => {
      const body = LoginRequestSchema.parse(values);
      const response = await apiRequest("/auth/login", AuthResponseSchema, {
        method: "POST",
        body: JSON.stringify(body),
        csrf: false,
      });
      if (response.csrf_token) setCsrfToken(response.csrf_token);
      return response;
    },
    onSuccess: (response) => queryClient.setQueryData(queryKeys.auth, response.user),
  });

  const logoutMutation = useMutation({
    mutationFn: () => apiRequest("/auth/logout", z.unknown(), { method: "POST" }),
    onSuccess: () => {
      setCsrfToken(null);
      queryClient.clear();
    },
  });

  const unauthorized = authQuery.error instanceof ApiError && authQuery.error.status === 401;

  return (
    <AuthContext.Provider
      value={{
        user: unauthorized ? null : (authQuery.data ?? null),
        isLoading: authQuery.isLoading,
        error: unauthorized ? null : (authQuery.error as Error | null),
        login: async (values) => (await loginMutation.mutateAsync(values)).user,
        logout: async () => {
          await logoutMutation.mutateAsync();
        },
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
