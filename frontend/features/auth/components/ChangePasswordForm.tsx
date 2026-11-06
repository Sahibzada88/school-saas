"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { AuthCard } from "@/features/auth/components/AuthCard";
import { useAuth } from "@/hooks/useAuth";
import { applyServerErrors } from "@/lib/forms";
import { homeRouteFor } from "@/lib/routes";
import { changePasswordSchema, type ChangePasswordValues } from "@/schemas/auth";

export function ChangePasswordForm() {
  const { user, changePassword, logout } = useAuth();
  const router = useRouter();
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ChangePasswordValues>({
    resolver: zodResolver(changePasswordSchema),
    defaultValues: { current_password: "", new_password: "", confirm_password: "" },
  });

  const onSubmit = handleSubmit(async ({ current_password, new_password }) => {
    setFormError(null);
    try {
      const me = await changePassword({ current_password, new_password });
      router.replace(homeRouteFor(me));
    } catch (error) {
      setFormError(applyServerErrors(error, setError, ["current_password", "new_password"]));
    }
  });

  const forced = user?.must_change_password ?? false;

  return (
    <AuthCard
      title="Change your password"
      description={
        forced
          ? "Your administrator set a temporary password. Choose a new one to continue."
          : "Choose a new password. Your other devices will be signed out."
      }
      footer={
        <button type="button" onClick={() => void logout()} className="font-medium text-foreground underline underline-offset-4">
          Sign out
        </button>
      }
    >
      <form onSubmit={onSubmit} noValidate className="space-y-4">
        {formError ? <FormAlert>{formError}</FormAlert> : null}
        <FormField
          label="Current password"
          type="password"
          autoComplete="current-password"
          error={errors.current_password?.message}
          {...register("current_password")}
        />
        <FormField
          label="New password"
          type="password"
          autoComplete="new-password"
          hint="At least 10 characters."
          error={errors.new_password?.message}
          {...register("new_password")}
        />
        <FormField
          label="Confirm new password"
          type="password"
          autoComplete="new-password"
          error={errors.confirm_password?.message}
          {...register("confirm_password")}
        />
        <Button type="submit" className="w-full" disabled={isSubmitting}>
          {isSubmitting ? <Loader2 className="size-4 animate-spin" /> : null} Update password
        </Button>
      </form>
    </AuthCard>
  );
}
