"use client";

import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  const dialogRef = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    const dialog = dialogRef.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      aria-describedby={description ? descriptionId : undefined}
      aria-labelledby={titleId}
      className="m-auto max-h-[calc(100dvh-2rem)] w-[min(42rem,calc(100%-2rem))] overflow-hidden rounded-2xl border border-border bg-surface p-0 text-foreground shadow-[0_28px_80px_rgb(3_18_32/0.28)] backdrop:bg-slate-950/55 backdrop:backdrop-blur-sm"
      onCancel={(event) => {
        event.preventDefault();
        onClose();
      }}
      onClose={onClose}
      ref={dialogRef}
    >
      <div className="flex max-h-[calc(100dvh-2rem)] flex-col">
        <header className="flex items-start gap-4 border-b border-border bg-surface-muted/75 px-5 py-4 sm:px-6">
          <div>
            <h2 className="font-heading text-lg font-semibold" id={titleId}>{title}</h2>
            {description ? <p className="mt-1 text-sm text-muted-foreground" id={descriptionId}>{description}</p> : null}
          </div>
          <button
            aria-label="Close dialog"
            className="icon-button -mr-2 ml-auto grid size-11 shrink-0 place-items-center rounded-xl text-muted-foreground hover:bg-surface-raised hover:text-foreground"
            onClick={onClose}
            type="button"
          >
            <X aria-hidden className="size-5" />
          </button>
        </header>
        <div className="overflow-y-auto px-5 py-5 sm:px-6">{children}</div>
        {footer ? <footer className="flex flex-wrap justify-end gap-2 border-t border-border bg-surface-muted/60 px-5 py-4 sm:px-6">{footer}</footer> : null}
      </div>
    </dialog>
  );
}
