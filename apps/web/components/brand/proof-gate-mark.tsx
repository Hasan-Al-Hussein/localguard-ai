import { cn } from "@/lib/cn";

type ProofGateMarkProps = {
  className?: string;
  decorative?: boolean;
  state?: "idle" | "verified" | "pending";
};

export function ProofGateMark({
  className,
  decorative = true,
  state = "verified",
}: ProofGateMarkProps) {
  const accessibility = decorative
    ? { "aria-hidden": true as const }
    : { "aria-label": "LocalGuard proof gate", role: "img" as const };

  return (
    <svg
      {...accessibility}
      className={cn("proof-gate-mark", className)}
      data-state={state}
      fill="none"
      viewBox="0 0 48 48"
      xmlns="http://www.w3.org/2000/svg"
    >
      <path className="proof-gate-bracket proof-gate-bracket-left" d="M19 9H12a3 3 0 0 0-3 3v24a3 3 0 0 0 3 3h7" />
      <path className="proof-gate-bracket proof-gate-bracket-right" d="M29 9h7a3 3 0 0 1 3 3v24a3 3 0 0 1-3 3h-7" />
      <path className="proof-gate-rail" d="M14 24h20" />
      <path className="proof-gate-core" d="m24 17 7 7-7 7-7-7 7-7Z" />
      <circle className="proof-gate-pulse" cx="24" cy="24" r="10.5" />
    </svg>
  );
}
