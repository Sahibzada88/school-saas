"use client";

import { Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { SelectField } from "@/components/common/SelectField";
import { Button } from "@/components/ui/button";
import { feeStructureHooks } from "@/features/school/resources";
import { applyServerErrors } from "@/lib/forms";
import { toOptions } from "@/lib/options";
import { useAllOptions } from "@/lib/resource";
import type { AcademicSession, FeeCategory, FeeStructure, SchoolClass } from "@/types/school";

interface Values { name: string; session: string; school_class: string; frequency: string; items: { category: string; amount: string }[] }

function Editor({ structure, onClose }: { structure: FeeStructure | null; onClose: () => void }) {
  const create = feeStructureHooks.useCreate();
  const update = feeStructureHooks.useUpdate();
  const sessions = useAllOptions<AcademicSession>("/school/sessions");
  const classes = useAllOptions<SchoolClass>("/school/classes");
  const categories = useAllOptions<FeeCategory>("/school/fees/categories");
  const [formError, setFormError] = useState<string | null>(null);
  const { register, control, handleSubmit, setError, watch, formState: { errors, isSubmitting } } = useForm<Values>({
    defaultValues: {
      name: structure?.name ?? "", session: structure?.session ?? sessions.options.find((s) => s.is_current)?.id ?? "", school_class: structure?.school_class ?? "",
      frequency: structure?.frequency ?? "MONTHLY", items: structure?.items.map((i) => ({ category: i.category, amount: i.amount })) ?? [{ category: "", amount: "" }],
    },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "items" });
  const total = (watch("items") ?? []).reduce((sum, i) => sum + (Number(i.amount) || 0), 0);

  const submit = handleSubmit(async (v) => {
    setFormError(null);
    const body = { ...v, school_class: v.school_class || null, items: v.items.filter((i) => i.category) };
    try {
      if (structure) await update.mutateAsync({ id: structure.id, body });
      else await create.mutateAsync(body);
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["name", "session", "school_class", "frequency", "items"]));
    }
  });

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Name" error={errors.name?.message} {...register("name", { required: "Required" })} />
        <SelectField label="Session" error={errors.session?.message} {...register("session", { required: "Required" })}><option value="">Choose…</option>{toOptions(sessions.options, (s) => s.name).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
        <SelectField label="Class" {...register("school_class")}><option value="">All classes</option>{toOptions(classes.options, (c) => c.name).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
        <SelectField label="Frequency" {...register("frequency")}>{["MONTHLY", "TERM", "ANNUAL", "ONE_TIME"].map((f) => <option key={f} value={f}>{f.replace("_", " ").toLowerCase()}</option>)}</SelectField>
      </div>
      <div className="space-y-2">
        <span className="text-sm font-medium">Fee items</span>
        {fields.map((field, index) => (
          <div key={field.id} className="grid grid-cols-[1fr_9rem_auto] items-end gap-2">
            <SelectField label="Category" hideLabel {...register(`items.${index}.category`)}><option value="">Category…</option>{toOptions(categories.options, (c) => c.name).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}</SelectField>
            <FormField label="Amount" aria-label="Amount" placeholder="Amount" inputMode="decimal" {...register(`items.${index}.amount`)} />
            <Button type="button" variant="ghost" size="icon" aria-label="Remove item" onClick={() => remove(index)} disabled={fields.length === 1}><Trash2 className="size-4" /></Button>
          </div>
        ))}
        <div className="flex items-center justify-between"><Button type="button" variant="outline" size="sm" onClick={() => append({ category: "", amount: "" })}><Plus className="size-4" /> Add item</Button><span className="text-sm font-medium">Total: {total.toFixed(2)}</span></div>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
        <Button type="submit" disabled={isSubmitting}>{isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null} Save structure</Button>
      </div>
    </form>
  );
}

export function StructureDialog({ target, onClose }: { target: "new" | FeeStructure | null; onClose: () => void }) {
  return (
    <Modal wide open={target !== null} title={target === "new" ? "New fee structure" : "Edit fee structure"} description="A structure lists the fees charged for a class and period. Invoices are generated from it." onClose={onClose}>
      {target ? <Editor key={target === "new" ? "new" : target.id} structure={target === "new" ? null : target} onClose={onClose} /> : null}
    </Modal>
  );
}
