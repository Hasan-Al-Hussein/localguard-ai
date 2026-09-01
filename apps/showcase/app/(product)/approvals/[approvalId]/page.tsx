import type { Metadata } from "next";
import { ApprovalDetailScreen } from "@/components/approvals/approval-detail-screen";
import { PUBLIC_DEMO_IDS } from "@/lib/public-demo";

export const metadata: Metadata = { title: "Review proposal" };
export const dynamicParams = false;

export function generateStaticParams() {
  return [{ approvalId: PUBLIC_DEMO_IDS.proposal }];
}

export default async function ApprovalDetailPage({
  params,
}: {
  params: Promise<{ approvalId: string }>;
}) {
  const { approvalId } = await params;
  return <ApprovalDetailScreen approvalId={approvalId} />;
}
