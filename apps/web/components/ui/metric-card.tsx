import { ArrowUpRight } from "lucide-react";
import type { ReactNode } from "react";
import Link from "next/link";

export function MetricCard({
  label,
  value,
  detail,
  icon,
  href,
  tone = "brand",
}: {
  label: string;
  value: string | number;
  detail?: string;
  icon: ReactNode;
  href?: string;
  tone?: "brand" | "evidence" | "pending" | "danger";
}) {
  const toneClasses = {
    brand: "bg-info-soft text-brand",
    evidence: "bg-evidence-soft text-evidence",
    pending: "bg-pending-soft text-pending",
    danger: "bg-danger-soft text-danger",
  } as const;

  const content = (
    <>
      <div className={`metric-icon grid size-10 place-items-center rounded-xl sm:size-11 ${toneClasses[tone]}`}>{icon}</div>
      {href ? <ArrowUpRight aria-hidden className="absolute top-5 right-5 size-4 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-brand" /> : null}
      <p className="mt-3 text-xs font-semibold text-muted-foreground sm:mt-4 sm:text-sm">{label}</p>
      <p className="tabular-nums mt-1 font-heading text-[1.85rem] leading-none font-bold tracking-[-0.045em] text-foreground sm:text-[2.15rem]">{value}</p>
      {detail ? <p className="mt-2 text-xs text-muted-foreground">{detail}</p> : null}
    </>
  );

  return href ? (
    <Link className="panel interactive-card metric-card group block min-h-32 p-4 sm:min-h-36 sm:p-4" href={href}>
      {content}
    </Link>
  ) : (
    <section className="panel metric-card relative min-h-32 p-4 sm:min-h-36 sm:p-4">{content}</section>
  );
}
