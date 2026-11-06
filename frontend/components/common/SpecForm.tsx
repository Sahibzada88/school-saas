"use client";

import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm, type UseFormSetValue } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { SelectField } from "@/components/common/SelectField";
import { TextareaField } from "@/components/common/TextareaField";
import { Button } from "@/components/ui/button";
import { applyServerErrors } from "@/lib/forms";
import { fileToDataUrl } from "@/lib/image";

export type FieldType = "text" | "email" | "tel" | "number" | "date" | "time" | "datetime" | "textarea" | "select" | "checkbox" | "password" | "image";

export interface FieldSpec {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: { value: string; label: string }[];
  placeholder?: string;
  hint?: string;
  nullable?: boolean; // empty -> null
  full?: boolean; // span both columns
  min?: number;
  max?: number;
  step?: string;
  readOnly?: boolean;
}

export type FormValues = Record<string, unknown>;

function defaults(fields: FieldSpec[], initial: FormValues = {}): FormValues {
  const out: FormValues = {};
  for (const field of fields) {
    const value = initial[field.name];
    if (field.type === "checkbox") out[field.name] = Boolean(value);
    else if (field.type === "image") out[field.name] = undefined;
    else if (field.type === "datetime") out[field.name] = value ? new Date(String(value)).toISOString().slice(0, 16) : "";
    else out[field.name] = value === null || value === undefined ? "" : String(value);
  }
  return out;
}

function normalize(fields: FieldSpec[], raw: FormValues, dirty: Record<string, unknown>): FormValues {
  const out: FormValues = {};
  for (const field of fields) {
    const value = raw[field.name];
    if (field.type === "image") {
      if (dirty[field.name]) out[field.name] = value ?? null; // null = remove, string = replace, absent = unchanged
    } else if (field.type === "checkbox") out[field.name] = Boolean(value);
    else if (field.type === "number") out[field.name] = value === "" || value === undefined ? (field.nullable ? null : "") : Number(value);
    else if (field.type === "datetime") out[field.name] = value === "" || value === undefined ? null : new Date(String(value)).toISOString();
    else out[field.name] = value === "" && field.nullable ? null : value;
  }
  return out;
}

function ImageField({ label, currentUrl, value, onPick, error }: { label: string; currentUrl?: string | null; value: unknown; onPick: (v: string | null) => void; error?: string }) {
  const [problem, setProblem] = useState<string | null>(null);
  const preview = value === null ? null : typeof value === "string" ? value : currentUrl;
  return (
    <div className="space-y-1.5">
      <span className="text-sm font-medium leading-none">{label}</span>
      <div className="flex items-center gap-3">
        {preview ? (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={preview} alt="" className="size-16 rounded-md border object-cover" />
        ) : (
          <div className="flex size-16 items-center justify-center rounded-md border border-dashed text-xs text-muted-foreground">None</div>
        )}
        <div className="space-y-1">
          <input
            type="file"
            accept="image/png,image/jpeg,image/webp"
            aria-label={label}
            className="text-sm"
            onChange={async (event) => {
              const file = event.target.files?.[0];
              if (!file) return;
              try {
                setProblem(null);
                onPick(await fileToDataUrl(file));
              } catch (error_) {
                setProblem(error_ instanceof Error ? error_.message : "Could not read that image.");
              }
            }}
          />
          {preview ? (
            <button type="button" className="text-xs text-muted-foreground underline" onClick={() => onPick(null)}>
              Remove
            </button>
          ) : null}
        </div>
      </div>
      {problem || error ? <p role="alert" className="text-sm text-destructive">{problem ?? error}</p> : null}
    </div>
  );
}

function SpecFormInner({
  fields, initial, submitLabel, onSubmit, onClose, imageUrls,
}: {
  fields: FieldSpec[];
  initial?: FormValues;
  submitLabel: string;
  onSubmit: (values: FormValues) => Promise<unknown>;
  onClose: () => void;
  imageUrls?: Record<string, string | null | undefined>;
}) {
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register, handleSubmit, setError, setValue, watch,
    formState: { errors, isSubmitting, dirtyFields },
  } = useForm<FormValues>({ defaultValues: defaults(fields, initial) });

  const submit = handleSubmit(async (raw) => {
    setFormError(null);
    try {
      await onSubmit(normalize(fields, raw, dirtyFields as Record<string, unknown>));
      onClose();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, fields.map((f) => f.name)));
    }
  });

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <div className="grid gap-4 sm:grid-cols-2">
        {fields.map((field) => {
          const error = errors[field.name]?.message as string | undefined;
          const rules = { required: field.required ? "This field is required" : false };
          const span = field.full || field.type === "textarea" || field.type === "image" ? "sm:col-span-2" : "";
          if (field.type === "select") {
            return (
              <div key={field.name} className={span}>
                <SelectField label={field.label} error={error} {...register(field.name, rules)}>
                  <option value="">{field.required ? "Choose…" : "None"}</option>
                  {(field.options ?? []).map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </SelectField>
              </div>
            );
          }
          if (field.type === "textarea") {
            return <div key={field.name} className={span}><TextareaField label={field.label} hint={field.hint} error={error} {...register(field.name, rules)} /></div>;
          }
          if (field.type === "checkbox") {
            return (
              <label key={field.name} className={`flex items-center gap-2 text-sm ${span}`}>
                <input type="checkbox" {...register(field.name)} /> {field.label}
              </label>
            );
          }
          if (field.type === "image") {
            return (
              <div key={field.name} className={span}>
                <ImageField
                  label={field.label}
                  currentUrl={imageUrls?.[field.name]}
                  value={watch(field.name)}
                  error={error}
                  onPick={(v) => (setValue as UseFormSetValue<FormValues>)(field.name, v as never, { shouldDirty: true })}
                />
              </div>
            );
          }
          return (
            <div key={field.name} className={span}>
              <FormField
                label={field.label}
                type={field.type === "datetime" ? "datetime-local" : field.type}
                placeholder={field.placeholder}
                hint={field.hint}
                min={field.min}
                max={field.max}
                step={field.step}
                readOnly={field.readOnly}
                autoComplete={field.type === "password" ? "new-password" : "off"}
                error={error}
                {...register(field.name, rules)}
              />
            </div>
          );
        })}
      </div>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose} disabled={isSubmitting}>Cancel</Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null} {submitLabel}
        </Button>
      </div>
    </form>
  );
}

/** Spec-driven create/edit dialog. Server-side validation errors are mapped onto the matching fields. */
export function SpecFormDialog({
  open, title, description, fields, initial, submitLabel = "Save", onSubmit, onClose, wide, imageUrls,
}: {
  open: boolean;
  title: string;
  description?: string;
  fields: FieldSpec[];
  initial?: FormValues;
  submitLabel?: string;
  onSubmit: (values: FormValues) => Promise<unknown>;
  onClose: () => void;
  wide?: boolean;
  imageUrls?: Record<string, string | null | undefined>;
}) {
  return (
    <Modal open={open} title={title} description={description} onClose={onClose} wide={wide}>
      <SpecFormInner fields={fields} initial={initial} submitLabel={submitLabel} onSubmit={onSubmit} onClose={onClose} imageUrls={imageUrls} />
    </Modal>
  );
}
