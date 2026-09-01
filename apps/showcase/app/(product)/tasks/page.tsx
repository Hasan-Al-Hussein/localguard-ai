import type { Metadata } from "next";
import { TasksScreen } from "@/components/tasks/tasks-screen";

export const metadata: Metadata = { title: "Workflow tasks" };

export default function TasksPage() {
  return <TasksScreen />;
}
