"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { SelectField } from "@/components/common/SelectField";
import { TextareaField } from "@/components/common/TextareaField";
import { Button } from "@/components/ui/button";
import { usePlans, useRecordPayment } from "@/features/platform/hooks";
import { applyServerErrors } from "@/lib/forms";
import { formatMoney } from "@/lib/format";
import { paymentSchema, type PaymentValues } from "@/schemas/billing";

const FIELDS = ["amount", "currency", "payment_method", "transaction_reference", "payment_date", "months", "plan", "notes"] as const;
const today = () => new Date().toISOString().slice(0, 10);

function PaymentForm({ schoolId, onClose }: { schoolId: string; onClose: () => void }) {
  const record = useRecordPayment();
  const plans = usePlans();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    watch,
    formState: { errors },
  } = useForm<PaymentValues>({
    resolver: zodResolver(paymentSchema),
    defaultValues: { amount: "", currency: "", transaction_reference: "", payment_date: today(), months: "1", plan: "", notes: "" },
  });

  const selectedPlan = plans.data?.find((p) => p.id === watch("plan"));
  const months = Number(watch("months")) || 1;

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await record.mutateAsync({
        school: schoolId,
        amount: values.amount,
        payment_method: values.payment_method,
        transaction_reference: values.transaction_reference,
        payment_date: values.payment_date,
        months: Number(values.months),
        notes: values.notes,
        ...(values.currency ? { currency: values.currency.toUpperCase() } : {}),
        ...(values.plan ? { plan: values.plan } : {}),
      });
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, FIELDS));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Amount received" inputMode="decimal" error={errors.amount?.message} {...register("amount")} />
        <FormField label="Currency" placeholder="Plan or school default" error={errors.currency?.message} {...register("currency")} />
        <SelectField label="Method" error={errors.payment_method?.message} {...register("payment_method")}>
          <option value="">Choose…</option>
          <option value="BANK_TRANSFER">Bank transfer</option>
          <option value="JAZZCASH">JazzCash</option>
          <option value="EASYPAISA">Easypaisa</option>
          <option value="CASH">Cash</option>
          <option value="OTHER">Other</option>
        </SelectField>
        <FormField label="Transaction reference" error={errors.transaction_reference?.message} {...register("transaction_reference")} />
        <FormField label="Payment date" type="date" error={errors.payment_date?.message} {...register("payment_date")} />
        <FormField label="Months covered" inputMode="numeric" error={errors.months?.message} {...register("months")} />
      </div>
      <SelectField label="Plan (optional: changes the school's plan)" error={errors.plan?.message} {...register("plan")}>
        <option value="">Keep current plan</option>
        {(plans.data ?? []).filter((p) => p.is_active).map((p) => (
          <option key={p.id} value={p.id}>
            {p.name}
          </option>
        ))}
      </SelectField>
      {selectedPlan ? (
        <p className="text-sm text-muted-foreground">
          List price: {formatMoney(Number(selectedPlan.monthly_price) * months, selectedPlan.currency)} for {months} month(s).
        </p>
      ) : null}
      <TextareaField label="Notes (optional)" error={errors.notes?.message} {...register("notes")} />
      <p className="text-sm text-muted-foreground">
        Recording this payment extends the subscription by the months covered and notifies the school admin.
      </p>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose} disabled={record.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={record.isPending}>
          {record.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Record payment
        </Button>
      </div>
    </form>
  );
}

export function RecordPaymentDialog({ schoolId, open, onClose }: { schoolId: string; open: boolean; onClose: () => void }) {
  return (
    <Modal wide open={open} title="Record a payment" description="Manual payment received outside the system." onClose={onClose}>
      <PaymentForm schoolId={schoolId} onClose={onClose} />
    </Modal>
  );
}
