import type { Metadata } from "next";
import { EvaluationDetailScreen } from "@/components/evaluations/evaluation-detail-screen";
import { PUBLIC_DEMO_IDS } from "@/lib/public-demo";

export const metadata: Metadata = { title: "Evaluation details" };
export const dynamicParams = false;

export function generateStaticParams() {
  return [{ runId: PUBLIC_DEMO_IDS.evaluationRun }];
}

export default async function EvaluationDetailPage({
  params,
}: {
  params: Promise<{ runId: string }>;
}) {
  const { runId } = await params;
  return <EvaluationDetailScreen runId={runId} />;
}
