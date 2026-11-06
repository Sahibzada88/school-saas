"use client";

import { useEffect, useRef, type ReactNode } from "react";

/** Accessible modal on the native <dialog> element (focus trap, Esc, backdrop). Children are mounted only while open,
 *  so forms start fresh each time. */
export function Modal({
  open,
  title,
  description,
  onClose,
  children,
  wide,
}: {
  open: boolean;
  title: string;
  description?: string;
  onClose: () => void;
  children: ReactNode;
  wide?: boolean;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) dialog.showModal();
    if (!open && dialog.open) dialog.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onClose={onClose}
      onClick={(event) => {
        if (event.target === ref.current) onClose(); // click on the backdrop
      }}
      className={`m-auto w-full ${wide ? "max-w-2xl" : "max-w-md"} rounded-lg border bg-card p-0 text-card-foreground shadow-lg backdrop:bg-black/50`}
    >
      {open ? (
        <div className="space-y-4 p-6">
          <div className="space-y-1">
            <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
            {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
          </div>
          {children}
        </div>
      ) : null}
    </dialog>
  );
}
