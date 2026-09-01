import type { Metadata } from "next";
import { AuditScreen } from "@/components/audit/audit-screen";

export const metadata: Metadata = { title: "Audit log" };

export default function AuditPage() {
  return <AuditScreen />;
}
