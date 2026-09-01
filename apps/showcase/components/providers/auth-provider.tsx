"use client";

import type { LoginRequest, User } from "@localguard/contracts";
import { PUBLIC_DEMO_IDS } from "@/lib/public-demo";
import { createContext, useContext, type ReactNode } from "react";

type AuthContextValue = {
  user: User;
  isLoading: false;
  error: null;
  login: (values: LoginRequest) => Promise<User>;
  logout: () => Promise<void>;
};

const publicDemoReviewer: User = {
  id: PUBLIC_DEMO_IDS.reviewer,
  username: "demo-reviewer",
  display_name: "Demo Reviewer",
  role: "reviewer",
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  return (
    <AuthContext.Provider
      value={{
        user: publicDemoReviewer,
        isLoading: false,
        error: null,
        login: async () => publicDemoReviewer,
        logout: async () => undefined,
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
