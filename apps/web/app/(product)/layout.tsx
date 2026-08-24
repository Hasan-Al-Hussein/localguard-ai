import type { ReactNode } from "react";
import { AuthGuard } from "@/components/shell/auth-guard";
import { ProductShell } from "@/components/shell/product-shell";

export default function ProductLayout({ children }: { children: ReactNode }) {
  return (
    <AuthGuard>
      <ProductShell>{children}</ProductShell>
    </AuthGuard>
  );
}
