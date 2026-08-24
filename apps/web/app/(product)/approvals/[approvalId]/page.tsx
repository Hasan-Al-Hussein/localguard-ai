import type { Metadata } from "next";
import { ApprovalDetailScreen } from "@/components/approvals/approval-detail-screen";

export const metadata: Metadata = { title: "Review proposal" };

export default async function ApprovalDetailPage({ params }: { params: Promise<{ approvalId: string }> }) {
  const { approvalId } = await params;
  return <ApprovalDetailScreen approvalId={approvalId} />;
}
