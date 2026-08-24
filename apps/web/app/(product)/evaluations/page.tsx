import type { Metadata } from "next";
import { EvaluationsScreen } from "@/components/evaluations/evaluations-screen";

export const metadata: Metadata = { title: "Evaluations" };

export default function EvaluationsPage() { return <EvaluationsScreen />; }
