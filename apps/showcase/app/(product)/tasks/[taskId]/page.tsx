import type { Metadata } from "next";
import { TaskDetailScreen } from "@/components/tasks/task-detail-screen";
import { PUBLIC_DEMO_IDS } from "@/lib/public-demo";

export const metadata: Metadata = { title: "Task details" };
export const dynamicParams = false;

export function generateStaticParams() {
  return [
    { taskId: PUBLIC_DEMO_IDS.createdTask },
    { taskId: PUBLIC_DEMO_IDS.historicalTask },
  ];
}

export default async function TaskDetailPage({
  params,
}: {
  params: Promise<{ taskId: string }>;
}) {
  const { taskId } = await params;
  return <TaskDetailScreen taskId={taskId} />;
}
