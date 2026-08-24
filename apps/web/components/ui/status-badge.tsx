import {
  Ban,
  CheckCircle2,
  CircleAlert,
  CircleDashed,
  Clock3,
  LoaderCircle,
  ShieldAlert,
} from "lucide-react";
import { cn } from "@/lib/cn";

const statusMap: Record<string, { label: string; className: string; icon: typeof CheckCircle2 }> = {
  ready: { label: "Ready", className: "bg-success-soft text-success", icon: CheckCircle2 },
  completed: { label: "Completed", className: "bg-success-soft text-success", icon: CheckCircle2 },
  approved: { label: "Approved", className: "bg-success-soft text-success", icon: CheckCircle2 },
  passed: { label: "Passed", className: "bg-success-soft text-success", icon: CheckCircle2 },
  success: { label: "Success", className: "bg-success-soft text-success", icon: CheckCircle2 },
  succeeded: { label: "Succeeded", className: "bg-success-soft text-success", icon: CheckCircle2 },
  measured: { label: "Measured", className: "bg-info-soft text-info", icon: CircleDashed },
  cited: { label: "Cited answer", className: "bg-evidence-soft text-evidence", icon: CheckCircle2 },
  strong: { label: "Strong evidence", className: "bg-evidence-soft text-evidence", icon: CheckCircle2 },
  partial: { label: "Partial evidence", className: "bg-pending-soft text-pending", icon: ShieldAlert },
  insufficient: { label: "Insufficient evidence", className: "bg-pending-soft text-pending", icon: ShieldAlert },
  summary_verified: { label: "Summary verified", className: "bg-info-soft text-info", icon: CheckCircle2 },
  run_verified: { label: "Run verified", className: "bg-evidence-soft text-evidence", icon: CheckCircle2 },
  current: { label: "Current contract", className: "bg-evidence-soft text-evidence", icon: CheckCircle2 },
  legacy_metadata_only: { label: "Legacy metadata", className: "bg-pending-soft text-pending", icon: ShieldAlert },
  unsupported_schema: { label: "Unsupported schema", className: "bg-pending-soft text-pending", icon: ShieldAlert },
  unavailable: { label: "Unavailable", className: "bg-surface-raised text-muted-foreground", icon: CircleDashed },
  not_applicable: { label: "Not applicable", className: "bg-surface-raised text-muted-foreground", icon: CircleDashed },
  corrupt: { label: "Corrupt artifact", className: "bg-danger-soft text-danger", icon: CircleAlert },
  hash_mismatch: { label: "Hash mismatch", className: "bg-danger-soft text-danger", icon: CircleAlert },
  pending: { label: "Pending", className: "bg-pending-soft text-pending", icon: Clock3 },
  queued: { label: "Queued", className: "bg-info-soft text-info", icon: Clock3 },
  processing: { label: "Processing", className: "bg-info-soft text-info", icon: LoaderCircle },
  running: { label: "Running", className: "bg-info-soft text-info", icon: LoaderCircle },
  uploaded: { label: "Uploaded", className: "bg-info-soft text-info", icon: Clock3 },
  validating: { label: "Validating", className: "bg-info-soft text-info", icon: LoaderCircle },
  extracting: { label: "Extracting", className: "bg-info-soft text-info", icon: LoaderCircle },
  chunking: { label: "Chunking", className: "bg-info-soft text-info", icon: LoaderCircle },
  indexing: { label: "Indexing", className: "bg-info-soft text-info", icon: LoaderCircle },
  classifying: { label: "Classifying", className: "bg-info-soft text-info", icon: LoaderCircle },
  retrieving: { label: "Retrieving", className: "bg-info-soft text-info", icon: LoaderCircle },
  drafting: { label: "Drafting", className: "bg-info-soft text-info", icon: LoaderCircle },
  failed: { label: "Failed", className: "bg-danger-soft text-danger", icon: CircleAlert },
  denied: { label: "Denied", className: "bg-danger-soft text-danger", icon: Ban },
  rejected: { label: "Rejected", className: "bg-danger-soft text-danger", icon: Ban },
  expired: { label: "Expired", className: "bg-surface-raised text-muted-foreground", icon: CircleDashed },
  open: { label: "Open", className: "bg-info-soft text-info", icon: CircleDashed },
  in_progress: { label: "In progress", className: "bg-pending-soft text-pending", icon: LoaderCircle },
  cancelled: { label: "Cancelled", className: "bg-surface-raised text-muted-foreground", icon: Ban },
};

export function StatusBadge({ status, className }: { status: string; className?: string }) {
  const configuration = statusMap[status] ?? {
    label: status.replaceAll("_", " "),
    className: "bg-surface-raised text-muted-foreground",
    icon: CircleDashed,
  };
  const Icon = configuration.icon;

  return (
    <span
      className={cn(
        "inline-flex min-h-7 items-center gap-1.5 rounded-full border border-current/10 px-2.5 py-1 text-xs font-semibold capitalize shadow-[inset_0_1px_0_rgb(255_255_255/.55)]",
        configuration.className,
        className,
      )}
    >
      <Icon
        aria-hidden
        className={cn("size-3.5", ["validating", "extracting", "chunking", "indexing", "processing", "running", "classifying", "retrieving", "drafting", "in_progress"].includes(status) && "animate-spin")}
      />
      {configuration.label}
    </span>
  );
}
