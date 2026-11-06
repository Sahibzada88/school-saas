"use client";

import { useState } from "react";

import { ConfirmDialog } from "@/components/common/ConfirmDialog";
import { FormField } from "@/components/common/FormField";
import { SelectField } from "@/components/common/SelectField";
import { TextareaField } from "@/components/common/TextareaField";
import { usePlans, useSubscriptionAction } from "@/features/platform/hooks";
import type { SubscriptionAction } from "@/features/platform/types";
import { serverMessage } from "@/lib/forms";

interface ActionCopy {
  title: string;
  description: string;
  confirm: string;
  days?: boolean;
  plan?: boolean;
  reason: "required" | "optional";
  destructive?: boolean;
  sendsConfirm?: boolean;
}

const COPY: Record<SubscriptionAction, ActionCopy> = {
  "extend-trial": { title: "Extend trial", description: "Adds days to the free trial (counted from today if it already ended).", confirm: "Extend trial", days: true, reason: "required" },
  extend: { title: "Extend subscription", description: "Adds free days to the paid period without recording a payment.", confirm: "Extend subscription", days: true, reason: "required" },
  "change-plan": { title: "Change plan", description: "Moves the school to another active plan. Limits change immediately.", confirm: "Change plan", plan: true, reason: "optional" },
  cancel: { title: "Cancel subscription", description: "The school keeps access until the paid period ends, then becomes read-only.", confirm: "Cancel subscription", reason: "required", destructive: true, sendsConfirm: true },
  suspend: { title: "Suspend subscription", description: "Blocks the school immediately until you resume the subscription.", confirm: "Suspend subscription", reason: "required", destructive: true, sendsConfirm: true },
  resume: { title: "Resume subscription", description: "Lifts the suspension. Access then follows the subscription dates.", confirm: "Resume subscription", reason: "optional" },
};

function ActionForm({ subscriptionId, action, onClose }: { subscriptionId: string; action: SubscriptionAction; onClose: () => void }) {
  const copy = COPY[action];
  const mutation = useSubscriptionAction(subscriptionId);
  const plans = usePlans();
  const [days, setDays] = useState("7");
  const [reason, setReason] = useState("");
  const [plan, setPlan] = useState("");

  const daysNumber = Number(days);
  const invalid =
    (copy.days && (!Number.isInteger(daysNumber) || daysNumber < 1 || daysNumber > (action === "extend-trial" ? 90 : 365))) ||
    (copy.plan && !plan) ||
    (copy.reason === "required" && reason.trim().length < 3);

  const submit = () =>
    mutation.mutate(
      {
        action,
        body: {
          ...(copy.days ? { days: daysNumber } : {}),
          ...(copy.plan ? { plan } : {}),
          reason: reason.trim(),
          ...(copy.sendsConfirm ? { confirm: true } : {}),
        },
      },
      { onSuccess: onClose },
    );

  return (
    <ConfirmDialog
      open
      title={copy.title}
      description={copy.description}
      confirmLabel={copy.confirm}
      destructive={copy.destructive}
      isPending={mutation.isPending}
      confirmDisabled={Boolean(invalid)}
      error={mutation.error ? serverMessage(mutation.error) : null}
      onConfirm={submit}
      onCancel={onClose}
    >
      {copy.days ? (
        <FormField label="Days" type="number" min={1} max={action === "extend-trial" ? 90 : 365} value={days} onChange={(e) => setDays(e.target.value)} />
      ) : null}
      {copy.plan ? (
        <SelectField label="New plan" value={plan} onChange={(e) => setPlan(e.target.value)}>
          <option value="">Choose a plan…</option>
          {(plans.data ?? []).filter((p) => p.is_active).map((p) => (
            <option key={p.id} value={p.id}>
              {p.name}
            </option>
          ))}
        </SelectField>
      ) : null}
      <TextareaField
        label={copy.reason === "required" ? "Reason (required)" : "Note (optional)"}
        value={reason}
        maxLength={500}
        onChange={(e) => setReason(e.target.value)}
        hint="Recorded in the audit log."
      />
    </ConfirmDialog>
  );
}

export function SubscriptionActionDialog({
  subscriptionId,
  action,
  onClose,
}: {
  subscriptionId: string;
  action: SubscriptionAction | null;
  onClose: () => void;
}) {
  if (!action) return null;
  return <ActionForm key={action} subscriptionId={subscriptionId} action={action} onClose={onClose} />;
}
