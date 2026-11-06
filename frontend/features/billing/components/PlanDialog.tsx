"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { TextareaField } from "@/components/common/TextareaField";
import { Button } from "@/components/ui/button";
import type { PlanInput } from "@/features/platform/api";
import { useCreatePlan, useUpdatePlan } from "@/features/platform/hooks";
import type { Plan } from "@/features/platform/types";
import { applyServerErrors } from "@/lib/forms";
import { planSchema, type PlanValues } from "@/schemas/billing";

const FIELDS = ["name", "slug", "description", "monthly_price", "currency", "max_students", "max_teachers", "max_classes", "features", "sort_order"] as const;
const toLimit = (value: string) => (value.trim() === "" ? null : Number(value));

function PlanForm({ plan, onClose }: { plan: Plan | null; onClose: () => void }) {
  const create = useCreatePlan();
  const update = useUpdatePlan();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<PlanValues>({
    resolver: zodResolver(planSchema),
    defaultValues: {
      name: plan?.name ?? "",
      slug: plan?.slug ?? "",
      description: plan?.description ?? "",
      monthly_price: plan?.monthly_price ?? "",
      currency: plan?.currency ?? "PKR",
      max_students: plan?.max_students?.toString() ?? "",
      max_teachers: plan?.max_teachers?.toString() ?? "",
      max_classes: plan?.max_classes?.toString() ?? "",
      features: (plan?.features ?? []).join("\n"),
      sort_order: plan ? String(plan.sort_order) : "0",
      is_active: plan?.is_active ?? true,
      is_public: plan?.is_public ?? true,
    },
  });
  const pending = create.isPending || update.isPending;

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    const body: PlanInput = {
      name: values.name,
      description: values.description,
      monthly_price: values.monthly_price,
      currency: values.currency.toUpperCase(),
      max_students: toLimit(values.max_students),
      max_teachers: toLimit(values.max_teachers),
      max_classes: toLimit(values.max_classes),
      features: values.features.split("\n").map((line) => line.trim()).filter(Boolean),
      sort_order: Number(values.sort_order),
      is_active: values.is_active,
      is_public: values.is_public,
    };
    try {
      if (plan) await update.mutateAsync({ id: plan.id, body });
      else await create.mutateAsync({ ...body, slug: values.slug });
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, FIELDS));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Name" error={errors.name?.message} {...register("name")} />
        <FormField
          label="Slug"
          readOnly={Boolean(plan)}
          hint={plan ? "Fixed after creation." : "Lowercase, e.g. standard"}
          error={errors.slug?.message}
          {...register("slug")}
        />
        <FormField label="Monthly price" inputMode="decimal" error={errors.monthly_price?.message} {...register("monthly_price")} />
        <FormField label="Currency" error={errors.currency?.message} {...register("currency")} />
        <FormField label="Max students" inputMode="numeric" hint="Empty = unlimited" error={errors.max_students?.message} {...register("max_students")} />
        <FormField label="Max teachers" inputMode="numeric" hint="Empty = unlimited" error={errors.max_teachers?.message} {...register("max_teachers")} />
        <FormField label="Max classes" inputMode="numeric" hint="Empty = unlimited" error={errors.max_classes?.message} {...register("max_classes")} />
        <FormField label="Sort order" inputMode="numeric" error={errors.sort_order?.message} {...register("sort_order")} />
      </div>
      <TextareaField label="Description" error={errors.description?.message} {...register("description")} />
      <TextareaField label="Features (one per line)" rows={4} error={errors.features?.message} {...register("features")} />
      <div className="flex flex-wrap gap-6 text-sm">
        <label className="flex items-center gap-2">
          <input type="checkbox" {...register("is_active")} /> Active (can be assigned)
        </label>
        <label className="flex items-center gap-2">
          <input type="checkbox" {...register("is_public")} /> Public (shown on pricing screens)
        </label>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose} disabled={pending}>
          Cancel
        </Button>
        <Button type="submit" disabled={pending}>
          {pending ? <Loader2 className="size-4 animate-spin" /> : null} {plan ? "Save changes" : "Create plan"}
        </Button>
      </div>
    </form>
  );
}

/** `target`: "create", an existing plan to edit, or null (closed). */
export function PlanDialog({ target, onClose }: { target: "create" | Plan | null; onClose: () => void }) {
  return (
    <Modal wide open={target !== null} title={target === "create" ? "New plan" : "Edit plan"} onClose={onClose}>
      {target ? <PlanForm key={target === "create" ? "create" : target.id} plan={target === "create" ? null : target} onClose={onClose} /> : null}
    </Modal>
  );
}
