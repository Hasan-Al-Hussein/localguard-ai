import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
}: {
  title: string;
  description: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <header className="page-header flex flex-col gap-4 border-b border-border pb-7 sm:flex-row sm:items-end sm:justify-between">
      <div className="max-w-3xl">
        {eyebrow ? <p className="mb-2.5 text-[0.7rem] font-bold tracking-[0.16em] text-evidence uppercase"><span aria-hidden className="eyebrow-dot" />{eyebrow}</p> : null}
        <h1 className="font-heading text-[1.8rem] leading-tight font-bold tracking-[-0.035em] text-foreground sm:text-[2.05rem]">{title}</h1>
        <p className="mt-2.5 max-w-2xl text-sm leading-6 text-muted-foreground sm:text-[0.98rem]">{description}</p>
      </div>
      {actions ? <div className="flex shrink-0 flex-wrap gap-2">{actions}</div> : null}
    </header>
  );
}
