"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";

import { FormAlert } from "@/components/common/FormAlert";
import { FormField } from "@/components/common/FormField";
import { Button } from "@/components/ui/button";
import { AuthCard } from "@/features/auth/components/AuthCard";
import { ApiError } from "@/lib/api-client";
import { applyServerErrors } from "@/lib/forms";
import { resetPasswordSchema, type ResetPasswordValues } from "@/schemas/auth";
import { authService } from "@/services/auth";

function tokenMessage(error: unknown): string | null {
  if (!(error instanceof ApiError)) return null;
  const messages = error.errors["token"];
  return Array.isArray(messages) && messages.length > 0 ? String(messages[0]) : null;
}

export function ResetPasswordForm() {
  const token = useSearchParams().get("token") ?? "";
  const [done, setDone] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<ResetPasswordValues>({
    resolver: zodResolver(resetPasswordSchema),
    defaultValues: { new_password: "", confirm_password: "" },
  });

  const onSubmit = handleSubmit(async ({ new_password }) => {
    setFormError(null);
    try {
      await authService.confirmPasswordReset({ token, new_password });
      setDone(true);
    } catch (error) {
      // "token" is not a visible field, so an invalid/expired link is shown at form level
      setFormError(tokenMessage(error) ?? applyServerErrors(error, setError, ["new_password"]));
    }
  });

  const footer = (
    <Link href="/login" className="font-medium text-foreground underline underline-offset-4">
      Back to sign in
    </Link>
  );

  if (!token) {
    return (
      <AuthCard title="Reset password" footer={footer}>
        <FormAlert>This reset link is missing its token. Request a new one from the sign-in page.</FormAlert>
      </AuthCard>
    );
  }

  return (
    <AuthCard title="Choose a new password" description="Your reset link can be used once." footer={footer}>
      {done ? (
        <FormAlert variant="success">Password updated. You can now sign in with your new password.</FormAlert>
      ) : (
        <form onSubmit={onSubmit} noValidate className="space-y-4">
          {formError ? <FormAlert>{formError}</FormAlert> : null}
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
      )}
    </AuthCard>
  );
}
