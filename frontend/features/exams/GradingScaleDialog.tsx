"use client";

import { Loader2, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { useFieldArray, useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { Button } from "@/components/ui/button";
import { gradingScaleHooks } from "@/features/school/resources";
import { applyServerErrors } from "@/lib/forms";
import type { GradeBand, GradingScale } from "@/types/school";

interface Values { name: string; is_default: boolean; bands: GradeBand[] }
const EMPTY_BAND: GradeBand = { grade: "", min_percent: "", max_percent: "", gpa_points: "0", remark: "", is_pass: true };

function Editor({ scale, onClose }: { scale: GradingScale | null; onClose: () => void }) {
  const create = gradingScaleHooks.useCreate();
  const update = gradingScaleHooks.useUpdate();
  const [formError, setFormError] = useState<string | null>(null);
  const { register, control, handleSubmit, setError, formState: { errors, isSubmitting } } = useForm<Values>({
    defaultValues: { name: scale?.name ?? "", is_default: scale?.is_default ?? false, bands: scale?.bands ?? [EMPTY_BAND] },
  });
  const { fields, append, remove } = useFieldArray({ control, name: "bands" });

  const submit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      if (scale) await update.mutateAsync({ id: scale.id, body: values });
      else await create.mutateAsync(values);
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["name", "bands"]));
    }
  });

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="Scale name" error={errors.name?.message} {...register("name", { required: "Required" })} />
        <label className="flex items-end gap-2 pb-2 text-sm"><input type="checkbox" {...register("is_default")} /> Default for new exams</label>
      </div>
      <div className="space-y-2">
        {fields.map((field, index) => (
          <div key={field.id} className="grid grid-cols-2 items-end gap-2 sm:grid-cols-[1fr_1fr_1fr_1fr_1.5fr_auto_auto]">
            <FormField label="Grade" {...register(`bands.${index}.grade`, { required: true })} />
            <FormField label="From %" inputMode="decimal" {...register(`bands.${index}.min_percent`, { required: true })} />
            <FormField label="To %" inputMode="decimal" {...register(`bands.${index}.max_percent`, { required: true })} />
            <FormField label="GPA" inputMode="decimal" {...register(`bands.${index}.gpa_points`)} />
            <FormField label="Remark" {...register(`bands.${index}.remark`)} />
            <label className="flex items-center gap-1 pb-2 text-xs"><input type="checkbox" {...register(`bands.${index}.is_pass`)} /> Pass</label>
            <Button type="button" variant="ghost" size="icon" aria-label="Remove grade" onClick={() => remove(index)} disabled={fields.length === 1}><Trash2 className="size-4" /></Button>
          </div>
        ))}
        <Button type="button" variant="outline" size="sm" onClick={() => append(EMPTY_BAND)}><Plus className="size-4" /> Add grade</Button>
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
        <Button type="submit" disabled={isSubmitting}>{isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null} Save scale</Button>
      </div>
    </form>
  );
}

export function GradingScaleDialog({ target, onClose }: { target: "new" | GradingScale | null; onClose: () => void }) {
  return (
    <Modal wide open={target !== null} title={target === "new" ? "New grading scale" : "Edit grading scale"} description="Ranges must not overlap. Results already published keep their grades until you recompute them." onClose={onClose}>
      {target ? <Editor key={target === "new" ? "new" : target.id} scale={target === "new" ? null : target} onClose={onClose} /> : null}
    </Modal>
  );
}
