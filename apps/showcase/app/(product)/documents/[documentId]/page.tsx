import type { Metadata } from "next";
import { Suspense } from "react";
import { DocumentViewerScreen } from "@/components/documents/document-viewer-screen";
import { PageSkeleton } from "@/components/ui/async-state";
import { PUBLIC_DEMO_IDS } from "@/lib/public-demo";

export const metadata: Metadata = { title: "Document viewer" };
export const dynamicParams = false;

export function generateStaticParams() {
  return [
    { documentId: PUBLIC_DEMO_IDS.vendorDocument },
    { documentId: PUBLIC_DEMO_IDS.incidentDocument },
    { documentId: PUBLIC_DEMO_IDS.evidenceDocument },
  ];
}

export default async function DocumentViewerPage({
  params,
}: {
  params: Promise<{ documentId: string }>;
}) {
  const { documentId } = await params;
  return (
    <Suspense fallback={<PageSkeleton />}>
      <DocumentViewerScreen documentId={documentId} />
    </Suspense>
  );
}
