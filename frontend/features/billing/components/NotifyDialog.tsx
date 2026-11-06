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
import { useNotifySchool } from "@/features/platform/hooks";
import { serverMessage } from "@/lib/forms";
import { notifySchema, type NotifyValues } from "@/schemas/billing";

function NotifyForm({ schoolId, onClose }: { schoolId: string; onClose: () => void }) {
  const notify = useNotifySchool(schoolId);
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<NotifyValues>({ resolver: zodResolver(notifySchema), defaultValues: { title: "", body: "", severity: "INFO" } });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await notify.mutateAsync(values);
      onClose();
    } catch (error) {
      setFormError(serverMessage(error));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <FormField label="Title" error={errors.title?.message} {...register("title")} />
      <TextareaField label="Message" error={errors.body?.message} {...register("body")} />
      <SelectField label="Importance" {...register("severity")}>
        <option value="INFO">Information</option>
        <option value="WARNING">Warning</option>
        <option value="CRITICAL">Critical</option>
      </SelectField>
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onClose} disabled={notify.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={notify.isPending}>
          {notify.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Send
        </Button>
      </div>
    </form>
  );
}

export function NotifyDialog({ schoolId, open, onClose }: { schoolId: string; open: boolean; onClose: () => void }) {
  return (
    <Modal open={open} title="Send a notification" description="Delivered to the school's administrators." onClose={onClose}>
      <NotifyForm schoolId={schoolId} onClose={onClose} />
    </Modal>
  );
}
