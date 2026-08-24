import type { Metadata } from "next";
import { DocumentViewerScreen } from "@/components/documents/document-viewer-screen";

export const metadata: Metadata = { title: "Document viewer" };

export default async function DocumentViewerPage({ params }: { params: Promise<{ documentId: string }> }) {
  const { documentId } = await params;
  return <DocumentViewerScreen documentId={documentId} />;
}
