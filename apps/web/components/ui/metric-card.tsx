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
      <div className={`metric-icon grid size-11 place-items-center rounded-xl ${toneClasses[tone]}`}>{icon}</div>
      {href ? <ArrowUpRight aria-hidden className="absolute top-5 right-5 size-4 text-muted-foreground transition-transform duration-200 group-hover:translate-x-0.5 group-hover:-translate-y-0.5 group-hover:text-brand" /> : null}
      <p className="mt-5 text-sm font-semibold text-muted-foreground">{label}</p>
      <p className="tabular-nums mt-1 font-heading text-[2.15rem] leading-none font-bold tracking-[-0.045em] text-foreground">{value}</p>
      {detail ? <p className="mt-2 text-xs text-muted-foreground">{detail}</p> : null}
    </>
  );

  return href ? (
    <Link className="panel interactive-card metric-card group block min-h-44 p-5" href={href}>
      {content}
    </Link>
  ) : (
    <section className="panel metric-card relative min-h-44 p-5">{content}</section>
  );
}
