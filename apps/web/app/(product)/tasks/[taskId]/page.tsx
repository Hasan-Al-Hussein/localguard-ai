import type { Metadata } from "next";
import { TaskDetailScreen } from "@/components/tasks/task-detail-screen";

export const metadata: Metadata = { title: "Task details" };

export default async function TaskDetailPage({ params }: { params: Promise<{ taskId: string }> }) {
  const { taskId } = await params;
  return <TaskDetailScreen taskId={taskId} />;
}
