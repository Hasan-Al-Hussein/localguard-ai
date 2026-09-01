import type { Metadata } from "next";
import { AuditEventScreen } from "@/components/audit/audit-event-screen";
import { PUBLIC_DEMO_IDS } from "@/lib/public-demo";

export const metadata: Metadata = { title: "Audit event" };
export const dynamicParams = false;

export function generateStaticParams() {
  return [
    { eventId: PUBLIC_DEMO_IDS.auditOverview },
    { eventId: PUBLIC_DEMO_IDS.auditDocument },
    { eventId: PUBLIC_DEMO_IDS.auditQuestion },
    { eventId: PUBLIC_DEMO_IDS.auditWorkflow },
    { eventId: PUBLIC_DEMO_IDS.auditApproval },
  ];
}

export default async function AuditEventPage({
  params,
}: {
  params: Promise<{ eventId: string }>;
}) {
  const { eventId } = await params;
  return <AuditEventScreen eventId={eventId} />;
}
