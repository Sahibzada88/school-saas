"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useState } from "react";
import { useForm, type UseFormRegisterReturn } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Modal } from "@/components/common/Modal";
import { SelectField } from "@/components/common/SelectField";
import { Button } from "@/components/ui/button";
import { useCreateUser, useUpdateUser } from "@/features/school/hooks";
import type { SchoolUser } from "@/features/school/types";
import { applyServerErrors } from "@/lib/forms";
import { SCHOOL_ROLE_OPTIONS } from "@/lib/roles";
import { createUserSchema, editUserSchema, type CreateUserValues, type EditUserValues } from "@/schemas/school";

function RoleSelect({ error, registration }: { error?: string; registration: UseFormRegisterReturn }) {
  return (
    <SelectField label="Role" error={error} {...registration}>
      <option value="">Choose a role…</option>
      {SCHOOL_ROLE_OPTIONS.map((option) => (
        <option key={option.value} value={option.value}>
          {option.label}
        </option>
      ))}
    </SelectField>
  );
}

function CreateForm({ onDone }: { onDone: () => void }) {
  const create = useCreateUser();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<CreateUserValues>({
    resolver: zodResolver(createUserSchema),
    defaultValues: { email: "", first_name: "", last_name: "", phone: "", password: "" },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await create.mutateAsync(values);
      onDone();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["email", "first_name", "last_name", "phone", "role", "password"]));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <FormField label="Email" type="email" autoComplete="off" error={errors.email?.message} {...register("email")} />
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="First name" error={errors.first_name?.message} {...register("first_name")} />
        <FormField label="Last name" error={errors.last_name?.message} {...register("last_name")} />
      </div>
      <FormField label="Phone (optional)" type="tel" error={errors.phone?.message} {...register("phone")} />
      <RoleSelect error={errors.role?.message} registration={register("role")} />
      <FormField
        label="Temporary password"
        type="password"
        autoComplete="new-password"
        hint="The user must change it at first sign-in."
        error={errors.password?.message}
        {...register("password")}
      />
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone} disabled={create.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={create.isPending}>
          {create.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Create user
        </Button>
      </div>
    </form>
  );
}

function EditForm({ user, isSelf, onDone }: { user: SchoolUser; isSelf: boolean; onDone: () => void }) {
  const update = useUpdateUser();
  const [formError, setFormError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<EditUserValues>({
    resolver: zodResolver(editUserSchema),
    defaultValues: { first_name: user.first_name, last_name: user.last_name, phone: user.phone, role: user.role as EditUserValues["role"] },
  });

  const onSubmit = handleSubmit(async (values) => {
    setFormError(null);
    try {
      await update.mutateAsync({ id: user.id, values });
      onDone();
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["first_name", "last_name", "phone", "role"]));
    }
  });

  return (
    <form onSubmit={onSubmit} noValidate className="space-y-4">
      {formError ? <FormAlert>{formError}</FormAlert> : null}
      <p className="text-sm text-muted-foreground">{user.email}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <FormField label="First name" error={errors.first_name?.message} {...register("first_name")} />
        <FormField label="Last name" error={errors.last_name?.message} {...register("last_name")} />
      </div>
      <FormField label="Phone (optional)" type="tel" error={errors.phone?.message} {...register("phone")} />
      <RoleSelect error={errors.role?.message} registration={register("role")} />
      {isSelf ? <p className="text-sm text-muted-foreground">You cannot change your own role; keep it as it is.</p> : null}
      <div className="flex justify-end gap-2">
        <Button type="button" variant="outline" onClick={onDone} disabled={update.isPending}>
          Cancel
        </Button>
        <Button type="submit" disabled={update.isPending}>
          {update.isPending ? <Loader2 className="size-4 animate-spin" /> : null} Save changes
        </Button>
      </div>
    </form>
  );
}

/** `target`: "create" opens the create form, a user opens the edit form, null keeps the dialog closed. */
export function UserFormDialog({
  target,
  currentUserId,
  onClose,
}: {
  target: "create" | SchoolUser | null;
  currentUserId: string | undefined;
  onClose: () => void;
}) {
  const open = target !== null;
  return (
    <Modal open={open} title={target === "create" ? "Add a user" : "Edit user"} onClose={onClose}>
      {target === "create" ? <CreateForm onDone={onClose} /> : null}
      {target && target !== "create" ? <EditForm user={target} isSelf={target.id === currentUserId} onDone={onClose} /> : null}
    </Modal>
  );
}
