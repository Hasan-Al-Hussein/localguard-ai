import type { Metadata } from "next";
import { AuditEventScreen } from "@/components/audit/audit-event-screen";

export const metadata: Metadata = { title: "Audit event" };

export default async function AuditEventPage({ params }: { params: Promise<{ eventId: string }> }) {
  const { eventId } = await params;
  return <AuditEventScreen eventId={eventId} />;
}
