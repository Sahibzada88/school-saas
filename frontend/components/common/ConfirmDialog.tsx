"use client";

import { Loader2 } from "lucide-react";
import type { ReactNode } from "react";

import { FormAlert } from "@/components/common/FormAlert";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";

export function ConfirmDialog({
  open,
  title,
  description,
  confirmLabel,
  destructive,
  isPending,
  error,
  confirmDisabled,
  onConfirm,
  onCancel,
  children,
}: {
  open: boolean;
  title: string;
  description?: string;
  confirmLabel: string;
  destructive?: boolean;
  isPending?: boolean;
  error?: string | null;
  confirmDisabled?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
  children?: ReactNode;
}) {
  return (
    <Modal open={open} title={title} description={description} onClose={onCancel}>
      {children}
      {error ? <FormAlert>{error}</FormAlert> : null}
      <div className="flex justify-end gap-2">
        <Button variant="outline" onClick={onCancel} disabled={isPending}>
          Cancel
        </Button>
        <Button variant={destructive ? "destructive" : "default"} onClick={onConfirm} disabled={isPending || confirmDisabled}>
          {isPending ? <Loader2 className="size-4 animate-spin" /> : null} {confirmLabel}
        </Button>
      </div>
    </Modal>
  );
}
