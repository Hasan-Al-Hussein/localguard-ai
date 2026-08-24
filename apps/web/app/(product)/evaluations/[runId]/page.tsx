import type { Metadata } from "next";
import { EvaluationDetailScreen } from "@/components/evaluations/evaluation-detail-screen";

export const metadata: Metadata = { title: "Evaluation details" };

export default async function EvaluationDetailPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  return <EvaluationDetailScreen runId={runId} />;
}
