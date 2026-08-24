import type { Metadata } from "next";
import { AuditScreen } from "@/components/audit/audit-screen";

export const metadata: Metadata = { title: "Audit log" };

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<{ thread?: string | string[] }>;
}) {
  const parameters = await searchParams;
  const threadId = typeof parameters.thread === "string" ? parameters.thread : undefined;
  return <AuditScreen threadId={threadId} />;
}
