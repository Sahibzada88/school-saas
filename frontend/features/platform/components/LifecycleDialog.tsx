"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { TextareaField } from "@/components/common/TextareaField";
import { ApiError } from "@/lib/api-client";

import { useSchoolTransition } from "../hooks";
import type { LifecycleAction } from "../types";

const COPY: Record<LifecycleAction, { title: string; confirm: string; body: string; reasonRequired: boolean; destructive: boolean }> = {
  suspend: {
    title: "Suspend school",
    confirm: "Suspend school",
    body: "The school's users will be blocked from the application until you reactivate it. No data is deleted.",
    reasonRequired: true,
    destructive: true,
  },
  deactivate: {
    title: "Deactivate school",
    confirm: "Deactivate school",
    body: "The school will be switched off. All data is kept and you can reactivate it at any time.",
    reasonRequired: true,
    destructive: true,
  },
  reactivate: {
    title: "Reactivate school",
    confirm: "Reactivate school",
    body: "The school's users will regain access immediately.",
    reasonRequired: false,
    destructive: false,
  },
};

/** Mounted only while open (Modal renders children lazily), so the reason field resets each time. */
function LifecycleForm({
  schoolId,
  schoolName,
  action,
  onClose,
}: {
  schoolId: string;
  schoolName: string;
  action: LifecycleAction;
  onClose: () => void;
}) {
  const copy = COPY[action];
  const mutation = useSchoolTransition(schoolId);
  const [reason, setReason] = useState("");
  const tooShort = copy.reasonRequired && reason.trim().length < 3;

  return (
    <ConfirmDialog
      open
      title={`${copy.title}: ${schoolName}`}
      description={copy.body}
      confirmLabel={copy.confirm}
      destructive={copy.destructive}
      isPending={mutation.isPending}
      confirmDisabled={tooShort}
      error={mutation.error instanceof ApiError ? mutation.error.message : mutation.error ? "Something went wrong." : null}
      onCancel={onClose}
      onConfirm={() => mutation.mutate({ action, reason: reason.trim() }, { onSuccess: onClose })}
    >
      <TextareaField
        label={copy.reasonRequired ? "Reason (required)" : "Note (optional)"}
        value={reason}
        maxLength={500}
        onChange={(event) => setReason(event.target.value)}
        hint="Recorded in the audit log."
      />
    </ConfirmDialog>
  );
}

export function LifecycleDialog({
  action,
  schoolId,
  schoolName,
  onClose,
}: {
  action: LifecycleAction | null;
  schoolId: string;
  schoolName: string;
  onClose: () => void;
}) {
  if (!action) return null;
  return <LifecycleForm key={action} schoolId={schoolId} schoolName={schoolName} action={action} onClose={onClose} />;
}
